import os
import urllib.request
import urllib.error
import json

# ตรวจสอบและอ่านค่าไฟล์ .env อย่างถูกต้องตามหลักภาษา Python
token = None
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            if "GITHUB_TOKEN" in line and "=" in line:
                # แยกส่วนคีย์และค่าออกจากกันก่อน แล้วจึงลบช่องว่างส่วนเกินบนค่าที่ได้
                parts = line.split("=", 1)
                if len(parts) == 2:
                    token = parts[1].strip().strip('"').strip("'")

# ตั้งค่าปลายทางไปที่ Endpoint ของ Rate Limit
url = "https://github.com"
req = urllib.request.Request(url)
req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
req.add_header("Accept", "application/vnd.github+json")

if token:
    masked = f"{token[:4]}...{token[-4:]}" if len(token) > 8 else "สั้นเกินไป"
    print(f"🤖 ตรวจพบ Token ใน .env: [{masked}] (ยาว {len(token)} ตัวอักษร)")
    req.add_header("Authorization", f"Bearer {token}")
else:
    print("⚠️ ไม่พบ GITHUB_TOKEN ในไฟล์ .env")

try:
    with urllib.request.urlopen(req) as response:
        raw_data = response.read().decode('utf-8')
        data = json.loads(raw_data)
        print("\n✅ เชื่อมต่อ API สำเร็จ! ผลลัพธ์โควตาของคุณ:")
        print(f"➡️ Core API (REST): {data['resources']['core']['remaining']}/{data['resources']['core']['limit']}")
        print(f"➡️ GraphQL API: {data['resources']['graphql']['remaining']}/{data['resources']['graphql']['limit']}")
except urllib.error.HTTPError as e:
    print(f"\n❌ GitHub API ปฏิเสธคำขอ (HTTP {e.code})")
    print(e.read().decode('utf-8', errors='ignore'))
except Exception as e:
    print(f"\n❌ ข้อผิดพลาดอื่นๆ: {e}")
