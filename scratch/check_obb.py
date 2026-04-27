from openbb import obb
import json
try:
    print(f"OBB System attributes: {json.dumps(dir(obb.system))}")
    # Try to find login
    for attr in dir(obb):
        if 'login' in attr.lower():
            print(f"Found login in obb: {attr}")
    for attr in dir(obb.user):
        if 'login' in attr.lower():
            print(f"Found login in obb.user: {attr}")
except Exception as e:
    print(f"Error: {e}")
