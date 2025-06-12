# cloud-function/gcf_entry.py

import subprocess
import functions_framework

@functions_framework.http
def main(request):
    try:
        result = subprocess.run(
            ["python3", "embed.py"],
            capture_output=True,
            text=True,
            check=True
        )
        return f"✅ embed.py executed successfully:\n{result.stdout}", 200
    except subprocess.CalledProcessError as e:
        return f"❌ embed.py failed:\n{e.stderr}", 500
