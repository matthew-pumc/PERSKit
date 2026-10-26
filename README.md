# PERSKit

独立运行的 JSONL 文档问答脚本。脚本将每条文档内容和 `queries.json` 中的问题发送到 OpenAI 兼容的 Chat Completions API，并将回答追加保存为 TSV。

## 文件

- `query_document.py`：处理脚本。
- `queries.json`：问题配置，可按需修改。
- `requirements.txt`：Python 第三方依赖。

## 环境准备

需要 Python 3.8 或更高版本，以及可访问的 DeepSeek/OpenAI 兼容 API 服务。

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

API 地址通过 `PERSKIT_API_URL` 环境变量配置，避免将内部地址写入并公开到源码中。也可以在运行时用 `--api-url` 覆盖环境变量；没有配置时脚本会报错退出。

```bash
export PERSKIT_API_URL="https://api.example.com/v1/chat/completions"
```

脚本使用模型名 `deepseek-v3`。

## 输入格式

`--input` 指定 JSONL 文件，每行一条 JSON 文档。建议包含文档 ID 和正文：

```json
{"article.uid":"WOS_000000000000001","content":"Document text"}
```

`article.uid` 用于输出文件名和断点续传；缺少时脚本会使用行号生成临时 ID。缺少 `content` 时，脚本会将整条 JSON 作为上下文。

## 运行

```bash
python3 query_document.py \
  --input input.jsonl \
  --queries queries.json \
  --output output.tsv \
  --error error_files.txt \
  --workers 8
```

`--input` 和 `--queries` 必填。`--output`、`--error`、`--workers`、`--delay` 可选；默认输出为 `output.tsv`，错误日志为 `error_files.txt`，并发数为 64，延迟为 0 秒。建议根据 API 服务能力调整并发数。

再次使用相同的输出文件运行时，脚本会跳过已经出现在 TSV 首列中的文档。输出文件不会自动写入列名表头。
