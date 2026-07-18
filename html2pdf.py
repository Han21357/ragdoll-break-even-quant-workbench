import weasyprint
import os

html_path = "/Users/solojyhan/Desktop/老布偶猫回本之路_项目交付包/02_老布偶猫回本之路_项目说明.html"
pdf_path = "/Users/solojyhan/Desktop/老布偶猫回本之路_项目交付包/01_老布偶猫回本之路_项目说明.pdf"

# 清除代理
for k in ['http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY','all_proxy','ALL_PROXY']:
    os.environ.pop(k, None)

print("Converting HTML to PDF...")
try:
    weasyprint.HTML(filename=html_path).write_pdf(pdf_path)
    size = os.path.getsize(pdf_path)
    print(f"OK: {pdf_path} ({size/1024:.0f} KB)")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
