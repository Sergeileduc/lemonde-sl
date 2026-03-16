"""Protocole ultra simple :
- entrée : une ligne JSON par job
- sortie : une ligne JSON par résultat
"""

import json
import sys
from pathlib import Path

from weasyprint import CSS, HTML


def render_pdf(html: str, css: str, output_path: str) -> dict:
    try:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        HTML(string=html).write_pdf(
            str(output),
            stylesheets=[CSS(string=css)],
        )
        return {"status": "ok", "output": str(output)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            job = json.loads(line)
            html = job["html"]
            css = job["css"]
            output = job["output"]
        except Exception as e:
            resp = {"status": "error", "error": f"invalid job: {e}"}
        else:
            resp = render_pdf(html, css, output)

        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()

if __name__ == "__main__":
    main()
