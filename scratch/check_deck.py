import re

with open('visualizations/codedee_presentation_rehearsal_deck.html', 'r', encoding='utf-8') as f:
    content = f.read()

# find slide titles
matches = re.findall(r'title:\s*["\']([^"\']+)["\']', content)
print(f"Total slides found: {len(matches)}")
for i, m in enumerate(matches, 1):
    print(f"Slide {i}: {m}")
