"""
检查 Flask 蓝图注册情况
运行方式: python check_blueprints.py
"""

from app import create_app

app = create_app()

print("=" * 70)
print("🔍 Flask 蓝图和路由检查")
print("=" * 70)

# 1. 检查所有注册的蓝图
print("\n1️⃣ 已注册的蓝图:")
if app.blueprints:
    for name, blueprint in app.blueprints.items():
        print(f"   ✅ {name}")
        print(f"      URL 前缀: {blueprint.url_prefix or '/'}")
else:
    print("   ❌ 没有注册任何蓝图")

# 2. 检查所有路由
print("\n2️⃣ 所有可用的路由:")
routes = []
for rule in app.url_map.iter_rules():
    routes.append({
        'endpoint': rule.endpoint,
        'methods': ','.join(rule.methods - {'HEAD', 'OPTIONS'}),
        'path': rule.rule
    })

# 按端点排序
routes.sort(key=lambda x: x['endpoint'])

for route in routes:
    print(f"   {route['endpoint']:<30} {route['methods']:<20} {route['path']}")

# 3. 检查特定的 TR 路由
print("\n3️⃣ TR 相关路由:")
tr_routes = [r for r in routes if r['endpoint'].startswith('tr.')]
if tr_routes:
    for route in tr_routes:
        print(f"   ✅ {route['endpoint']:<30} {route['path']}")
else:
    print("   ❌ 没有找到 TR 相关路由")
    print("   💡 这意味着 TR 蓝图没有正确注册")

# 4. 测试 URL 构建
print("\n4️⃣ 测试 URL 构建:")
with app.app_context():
    test_endpoints = [
        'tr.index',
        'tr.new_tr',
        'tr.edit_tr',
    ]

    for endpoint in test_endpoints:
        try:
            if endpoint == 'tr.edit_tr':
                url = app.url_for(endpoint, tr_id=1)
            else:
                url = app.url_for(endpoint)
            print(f"   ✅ {endpoint:<30} → {url}")
        except Exception as e:
            print(f"   ❌ {endpoint:<30} → 错误: {e}")

print("\n" + "=" * 70)
print("✅ 检查完成")
print("=" * 70)

# 5. 诊断建议
print("\n💡 诊断建议:")

if not app.blueprints:
    print("   ❌ 没有注册蓝图！")
    print("   解决：检查 app/__init__.py 中的蓝图注册代码")
elif 'tr' not in app.blueprints:
    print("   ❌ TR 蓝图未注册！")
    print("   解决：在 app/__init__.py 中添加：")
    print("        from app.blueprints.tr import tr_bp")
    print("        app.register_blueprint(tr_bp, url_prefix='/tr')")
elif not tr_routes:
    print("   ❌ TR 蓝图已注册但没有路由！")
    print("   解决：检查 app/blueprints/tr/routes.py 是否正确导入")
else:
    print("   ✅ 一切正常！")