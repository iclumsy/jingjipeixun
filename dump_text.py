from docx import Document
doc = Document('training_system/template.docx')
text = []
for t in doc.tables:
    for r in t.rows:
        for c in r.cells:
            text.append(c.text.strip())
print(" | ".join(text))
