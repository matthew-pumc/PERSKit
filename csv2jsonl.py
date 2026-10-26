import pandas as pd
import json
import argparse

def csv_to_jsonl(csv_file, jsonl_file, filter_empty_doi=False):
    """
    Convert a CSV or TSV file to JSON Lines format using pandas.
    Optionally filter out rows where 'article.doi' is empty.
    """
    try:
        # 自动检测分隔符
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            sample = f.read(4096)
            delimiter = ',' if ',' in sample and sample.count(',') >= sample.count('\t') else '\t'
        print(f"Detected delimiter: '{delimiter}'")

        df = pd.read_csv(csv_file, delimiter=delimiter, dtype=str, encoding='utf-8-sig')
        total_rows = len(df)
        empty_doi_count = df['article.doi'].isna().sum() + (df['article.doi'] == '').sum() if 'article.doi' in df.columns else 0

        if filter_empty_doi and 'article.doi' in df.columns:
            df = df[df['article.doi'].notna() & (df['article.doi'].str.strip() != '')]

        df.to_json(jsonl_file, orient='records', lines=True, force_ascii=False)
        jsonl_lines = sum(1 for _ in open(jsonl_file, encoding='utf-8'))

        print(f"Conversion complete. {jsonl_lines} lines saved to: {jsonl_file}")
        print(f"CSV data rows: {total_rows}, JSONL lines: {jsonl_lines}")
        print(f"Rows with empty article.doi: {empty_doi_count}")
        if (total_rows - empty_doi_count if filter_empty_doi else total_rows) != jsonl_lines:
            print("Warning: csv and jsonl line counts do not match. Check for filtering issues.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert CSV/TSV to JSONL using pandas. Optionally filter out rows where 'article.doi' is empty.")
    parser.add_argument("input", help="Input CSV or TSV file")
    parser.add_argument("output", help="Output JSONL file")
    parser.add_argument("--filter-empty-doi", action="store_true", help="Filter out rows where 'article.doi' is empty")
    args = parser.parse_args()
    csv_to_jsonl(args.input, args.output, filter_empty_doi=args.filter_empty_doi)