#!/usr/bin/env python3
"""
query_document_v0.6.py
version 0.6: skip embedding, direct query to Deepseek API, submit all queries in one prompt
version 0.5: removed process directory, now only process jsonl files, use BytesIO to upload content directly
version 0.4: added support for continuous processing when error occurs
version 0.3: added support for processing jsonl files and save output while processing
version 0.2: updated to parallelize the processing of documents
version 0.1: initial version, supports processing a directory of documents

author: matthew
date: 2025-08-17
"""

import argparse
import json
import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from uuid import uuid4
from string import Template

import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm

# ---------- 日志 ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------- 全局会话 ----------
session = requests.Session()
# 增大连接池容量，适配高并发
adapter = HTTPAdapter(pool_connections=10, pool_maxsize=150)
session.mount("http://", adapter)
session.mount("https://", adapter)
session.headers.update({"Content-Type": "application/json"})

# ---------- PROMPT 模板 ----------
BASE_PROMPT = Template("""
You are an expert assistant whose job is to answer the following questions using ONLY the information provided in the Context.

---

Questions:
$questions_block

---

Context:
$context

---

Instructions:
- Answer each question strictly based on the context.
- Format your response as a JSON object: {"answer": [q1_answer, q2_answer, ...]}
- If an answer is not present, respond with "None" for that question.
- If you cannot answer, still respond in the required JSON format.
- Do not output anything except the JSON object.
""")

# ---------- 单文件处理 ----------
def handle_one_file(idx_line, queries, delay, output_file, error_log, api_url):
    idx, line = idx_line
    try:
        data = json.loads(line)
        uid = str(data.get("article.uid", f"temp_{idx}"))
        fname = f"{uid}.txt"
        context = data.get("content", json.dumps(data, ensure_ascii=False, indent=2))

        questions_block = "\n".join(
            [f"{i+1}. ({entity_type}) {query}" for i, (entity_type, query) in enumerate(queries.items())]
        )
        prompt = BASE_PROMPT.substitute(
            questions_block=questions_block,
            context=context
        )

        payload = {
            "model": "deepseek-v3",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
            "temperature": 0.0,
        }

        time.sleep(delay)
        for attempt in range(3):
            try:
                r = requests.post(
                    api_url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=30
                )
                r.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                logger.error(f"idx={idx}: attempt {attempt+1} failed: {e}")
                time.sleep(5)
        else:
            with open(error_log, "a", encoding="utf-8") as ef:
                ef.write(f"{idx}\tReadTimeout\n")
            return False

        raw = r.json()["choices"][0]["message"]["content"].strip()

        if not raw:
            logger.error(f"idx={idx}: Model returned empty content.")
            with open(error_log, "a", encoding="utf-8") as ef:
                ef.write(f"{idx}\tEMPTY_RESPONSE\n")
            return False

        try:
            answers = json.loads(raw)["answer"]
        except Exception:
            logger.error(f"idx={idx}: Model response not valid JSON: {raw}")
            with open(error_log, "a", encoding="utf-8") as ef:
                ef.write(f"{idx}\t{raw}\n")
            return False

        headers = ["filename"] + list(queries.keys())
        row_values = [fname] + [answers[i] if i < len(answers) else "" for i in range(len(queries))]
        with open(output_file, "a", encoding="utf-8", buffering=1) as f:
            f.write("\t".join(str(v) for v in row_values) + "\n")
        return True

    except Exception as e:
        logger.error(f"idx={idx}: {e}")
        with open(error_log, "a", encoding="utf-8") as ef:
            ef.write(f"{idx}\t{e}\n")
        return False

# ---------- 主处理流程 ----------
def process_jsonl_and_upload(jsonl_path, queries, delay, output_file, error_log, max_workers, api_url):
    headers = ["filename"] + list(queries.keys())

    # 断点续传：已完成的文件名
    done_files = set()
    if os.path.exists(output_file):
        with open(output_file, encoding="utf-8") as f:
            done_files = {line.split("\t", 1)[0].strip() for line in f if line.strip()}

    with open(jsonl_path, encoding="utf-8") as f:
        lines = f.readlines()

    todo = [
        (idx, line)
        for idx, line in enumerate(lines)
        if f"{str(json.loads(line).get('article.uid', f'temp_{idx}'))}.txt" not in done_files
    ]

    if not todo:
        logger.info("All files already processed.")
        return

    with ThreadPoolExecutor(max_workers=max_workers) as exe, \
         open(output_file, "a", encoding="utf-8", buffering=1) as f_out:
        with tqdm(total=len(todo), desc="Processing") as pbar:
            future_to_task = {
                exe.submit(handle_one_file, t, queries, delay, output_file, error_log, api_url): t
                for t in todo
            }
            for future in as_completed(future_to_task):
                # 进度条立即刷新
                pbar.update(1)

# ---------- CLI ----------
def main():
    parser = argparse.ArgumentParser(description="Query documents in a JSONL file using Deepseek API.")
    parser.add_argument("--input", required=True, help="JSONL file")
    parser.add_argument("--queries", required=True, help="queries.json")
    parser.add_argument("--output", default="output.tsv")
    parser.add_argument("--error", default="error_files.txt")
    parser.add_argument("--workers", type=int, default=64)
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument(
        "--api-url",
        default=os.environ.get("PERSKIT_API_URL"),
        help="Chat Completions endpoint (default: PERSKIT_API_URL environment variable)",
    )
    args = parser.parse_args()

    if not args.api_url:
        parser.error("set PERSKIT_API_URL or provide --api-url")

    with open(args.queries, encoding="utf-8") as f:
        queries = json.load(f)

    process_jsonl_and_upload(
        jsonl_path=args.input,
        queries=queries,
        delay=args.delay,
        output_file=args.output,
        error_log=args.error,
        max_workers=args.workers,
        api_url=args.api_url,
    )

if __name__ == "__main__":
    main()