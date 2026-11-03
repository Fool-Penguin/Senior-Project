import pandas as pd

df = pd.read_parquet('datasets/original/hitoshura25_cvefixes_all.parquet')
web_df = df[df['language'].isin(['Python', 'JavaScript', 'TypeScript'])]
print('Total web rows in cvefixes_all:', len(web_df))

queries = ['mongo', 'nosql', 'couch', r'\$gt', r'\$ne', r'\$where']
for q in queries:
    m = web_df[
        web_df['vulnerable_code'].astype(str).str.contains(q, case=False, na=False) |
        web_df['repo_url'].astype(str).str.contains(q, case=False, na=False)
    ]
    print(f'Query "{q}": {len(m)} matches')
    if len(m) > 0:
        for idx, r in m.head(5).iterrows():
            print(f"   {r['cve_id']} | {r['language']} | {r['cwe_id']} | {r['repo_url']}")
