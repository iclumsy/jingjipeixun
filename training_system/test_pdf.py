"""调试"""
import re, weasyprint

with open('logs/print_page.html', 'r', encoding='utf-8') as f:
    raw_html = f.read()

html = raw_html
html = html.replace("src='image.do", "src='http://www.sxtsks.com/image.do")
html = html.replace('src="image.do', 'src="http://www.sxtsks.com/image.do')
html = re.sub(r'<link[^>]+href=["\']css/[^"\']+["\'][^>]*/?\s*>', '', html)
html = re.sub(r'<script[^>]+src=["\'][^"\']+["\'][^>]*>\s*</script>', '', html)
html = re.sub(r'<script[\s\S]*?</script>', '', html)
html = html.replace('onLoad="loadpage()"', '')
html = html.replace('class="noprint"', 'class="noprint" style="display:none"')
html = re.sub(r'<style type="text/css">\s*body\{.*?</style>', '', html, flags=re.S)
html = re.sub(r'<style type="text/css" media="print">.*?</style>', '', html, flags=re.S)
html = html.replace('width="650"', '')
html = html.replace('width="650px"', '')

inject_css = """<style>
@page { size: A4; margin: 15mm; }
body {
    font-size: 12pt;
    font-family: "PingFang SC","Microsoft YaHei","Helvetica Neue",sans-serif;
    margin: 0; padding: 0; box-sizing: border-box;
}
.tit1 {
    padding: 0 0 10px 0; line-height: 36pt; text-align: center;
    font-size: 18pt; font-weight: normal;
    font-family: "PingFang SC","Microsoft YaHei","Helvetica Neue",sans-serif;
}
.tbsd {
    border: 1px solid #000;
    width: 100%; border-collapse: collapse; margin: 0 auto;
    table-layout: fixed; box-sizing: border-box;
}
/* 列宽分配：第二列缩小，第四列增大，确保身份证放得下一行，右侧区域够宽 */
.tbsd tr:first-child td:nth-child(1) { width: 20%; }
.tbsd tr:first-child td:nth-child(2) { width: 32%; }
.tbsd tr:first-child td:nth-child(3) { width: 15%; }
.tbsd tr:first-child td:nth-child(4) { width: 15%; }
.tbsd tr:first-child td:nth-child(5) { width: 18%; }

.tbsd td {
    font-size: 12pt; padding: 6px 4px; line-height: 16pt;
    border: 1px solid #000; box-sizing: border-box;
    font-family: "PingFang SC","Microsoft YaHei","Helvetica Neue",sans-serif;
    word-break: break-all; vertical-align: middle;
}
.tbsd td p { font-size: 12pt; font-family: "PingFang SC","Microsoft YaHei","Helvetica Neue",sans-serif; margin:0;}
td[height="84"] { height: 64pt; } 
td[height="115"] { height: 85pt; } 

table { width: 100%; border-collapse: collapse; }
img { max-width: 86px; max-height: 125px; display: block; margin: 0 auto; }
.noprint, .Noprint { display: none !important; }
input[type="hidden"] { display: none; }
strong { font-weight: bold; font-family: "PingFang SC","Microsoft YaHei",sans-serif; font-size: 9pt; }
div[align="right"] { font-size: 9pt; text-align: right; margin-right: 20px; }
div[align="left"] { font-size: 9pt; text-align: left; margin-left: 10px; }
</style>"""
html = html.replace('</head>', inject_css + '</head>')

id_card_match = re.search(r'身份证件号\s*</td>\s*<td[^>]*>\s*([0-9X]{18})', html, re.I)
if id_card_match:
    id_card = id_card_match.group(1)
    gender_char = id_card[16:17]
    gender_str = '女' if int(gender_char) % 2 == 0 else '男'
    html = re.sub(r'(>性别\s*</td>\s*<td[^>]*>)\s*&nbsp;\s*</td>', f'\\g<1>{gender_str}</td>', html)

wm_match = re.search(r"watermark\.innerText\s*=\s*'([^']+)'", raw_html)
wm_text = wm_match.group(1) if wm_match else '山西省特种设备作业人员考核管理平台'

watermark_html = f'<div style="position:fixed; top:105mm; left:15mm; font-size:20pt; font-family:PingFang SC,Microsoft YaHei,sans-serif; color:#a1a1ab; white-space:nowrap; z-index:-10;">{wm_text}</div>'
html = re.sub(r'(<body[^>]*>)', r'\1' + watermark_html, html, count=1)

pdf = weasyprint.HTML(string=html).write_pdf()
with open('logs/申请表-test.pdf', 'wb') as f:
    f.write(pdf)
print("done")
