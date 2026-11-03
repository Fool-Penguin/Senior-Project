import yaml, json, csv

print("=== 1. security_vulnerability_catalogue.yaml INCLUSIONS ===")
with open('data/security_vulnerability_catalogue.yaml', 'r', encoding='utf-8') as f:
    cat = yaml.safe_load(f)
for inc in cat.get('inclusions', []):
    cwe = inc.get('cwe_id')
    name = inc.get('name')
    owasp_w = inc.get('owasp_web')
    owasp_l = inc.get('owasp_llm')
    print(f"{inc.get('id'):15} | {str(cwe):10} | {str(owasp_w or owasp_l):35} | {name[:45]}")

print("\n=== 2. Taxonomy_table.csv ===")
with open('Taxonomy_table.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for r in reader:
        print(f"{r['No.']:3} | {r['Type']:35} | {r['Name']:35} | {r['References']}")

print("\n=== 3. codedee_security_dataset_catalogue_scope.json unique pairs ===")
with open('datasets/unified/codedee_security_dataset_catalogue_scope.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
pairs = set()
for item in data:
    pairs.add((item.get('cwe_id'), item.get('cwe_name'), item.get('owasp_category')))
for cwe, name, owasp in sorted(pairs, key=lambda x: str(x[0])):
    print(f"{str(cwe):10} | {str(owasp):45} | {str(name)}")
