import sys
from pathlib import Path

# Add server to sys.path
SERVER_DIR = Path("d:/4th-year/Senior-Project/codedee/codedee_server")
sys.path.insert(0, str(SERVER_DIR))

from app.taint.walker import SymbolicTaintWalker

walker = SymbolicTaintWalker()

# Test 1: Nested subscript chaining container[0][0]
c1 = '''
from flask import request
def test1():
    user = request.args.get('u')
    box = [[user]]
    sql = f"SELECT * FROM t WHERE x = {box[0][0]}"
    cursor.execute(sql)
'''
f1 = walker.analyze_code(c1, 'python', 't1.py')
v1 = [f for f in f1 if not f.sanitized and f.severity == 'CRITICAL']
assert len(v1) >= 1, f"Nested subscript failed! Found: {len(v1)}"
print("Scenario 1 (Nested subscript box[0][0]) -> PASSED")

# Test 2: Method call with keyword arguments
c2 = '''
from flask import request
def test2():
    user = request.args.get('u')
    clean = user.replace(old="'", new="''")
    sql = f"SELECT * FROM t WHERE x = {clean}"
    cursor.execute(sql)
'''
f2 = walker.analyze_code(c2, 'python', 't2.py')
v2 = [f for f in f2 if not f.sanitized and f.severity == 'CRITICAL']
assert len(v2) >= 1, f"Method call with kwargs failed! Found: {len(v2)}"
print("Scenario 2 (Method call with kwargs) -> PASSED")

# Test 3: Multiline empty tuple bypass
c3 = '''
from flask import request
def test3():
    user = request.args.get('u')
    sql = f"SELECT * FROM t WHERE x = {user}"
    cursor.execute(sql, (
    ))
'''
f3 = walker.analyze_code(c3, 'python', 't3.py')
v3 = [f for f in f3 if not f.sanitized and f.severity == 'CRITICAL']
assert len(v3) >= 1, f"Multiline empty tuple failed! Found: {len(v3)}"
print("Scenario 3 (Multiline empty tuple) -> PASSED")

# Test 4: Genuine parameterized query with multiple parameters
c4 = '''
from flask import request
def test4():
    user = request.args.get('u')
    role = request.args.get('r')
    cursor.execute('SELECT * FROM t WHERE u = %s AND r = %s', (user, role))
'''
f4 = walker.analyze_code(c4, 'python', 't4.py')
assert all(f.sanitized is True for f in f4), f"Legitimate parameterized query was falsely flagged! {f4}"
print("Scenario 4 (Genuine parameterized query) -> PASSED")

# Test 5: Nested dictionary access data['a']['b']
c5 = '''
from flask import request
def test5():
    user = request.args.get('u')
    data = {"a": {"b": user}}
    sql = "SELECT * FROM t WHERE u = '%s'" % data['a']['b']
    cursor.execute(sql)
'''
f5 = walker.analyze_code(c5, 'python', 't5.py')
v5 = [f for f in f5 if not f.sanitized and f.severity == 'CRITICAL']
assert len(v5) >= 1, f"Nested dict access failed! Found: {len(v5)}"
print("Scenario 5 (Nested dict access data['a']['b']) -> PASSED")

# Test 6: Python async method receiver call
c6 = '''
from flask import request
async def test6():
    user = request.args.get('u')
    clean = user.strip()
    query = f"SELECT * FROM t WHERE x = '{clean}'"
    await cursor.execute(query)
'''
f6 = walker.analyze_code(c6, 'python', 't6.py')
v6 = [f for f in f6 if not f.sanitized and f.severity == 'CRITICAL']
assert len(v6) >= 1, f"Async method receiver failed! Found: {len(v6)}"
print("Scenario 6 (Async method receiver + await sink) -> PASSED")

print("\nALL 6 ADVERSARIAL STRESS SCENARIOS SUCCEEDED!")
