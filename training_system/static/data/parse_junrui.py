import re
import json
import os

def parse_md(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 规范化换行
    content = content.replace('\r\n', '\n')
    
    # 按题型分割
    sections = re.split(r'\n##\s+(单选题|多选题|判断题)', '\n' + content)
    
    all_questions = []
    
    for i in range(1, len(sections), 2):
        type_name = sections[i]
        section_content = sections[i+1]
        
        type_code = 1
        if '多选题' in type_name:
            type_code = 2
        elif '判断题' in type_name:
            type_code = 3
            
        # 按题目分割
        q_blocks = re.split(r'\n###\s+第\s+\d+\s+题', '\n' + section_content)
        
        type_count = 0
        for q_block in q_blocks:
            q_block = q_block.strip()
            if not q_block:
                continue
                
            # 解析 ID
            id_match = re.search(r'-\s+\*\*题目\s*ID\*\*:\s*`(\d+)`', q_block)
            if not id_match:
                id_match = re.search(r'-\s+\*\*题目\s*ID\*\*:\s*(\d+)', q_block)
            q_id = int(id_match.group(1)) if id_match else 0
            
            # 解析题目内容和图片
            # 兼容题目中的图片: ![题目图片](forklift_assets/...)
            q_text_match = re.search(r'-\s+\*\*题目\*\*:\s*(.*?)(?=\n\s*-)', q_block, re.DOTALL)
            question_text = ""
            question_images = []
            if q_text_match:
                raw_text = q_text_match.group(1).strip()
                # 提取图片路径
                img_matches = re.findall(r'!\[.*?\]\((.*?)\)', raw_text)
                for img in img_matches:
                    # 只取文件名，去除路径前缀
                    fname = os.path.basename(img)
                    question_images.append(fname)
                # 清理掉文本中的图片语法
                question_text = re.sub(r'!\[.*?\]\(.*?\)', '[图片]', raw_text)
            
            # 解析选项
            options = {}
            opt_section_match = re.search(r'-\s+\*\*选项\*\*:\s*\n(.*?)(?=\n\s*-\s+\*\*标准答案\*\*)', q_block, re.DOTALL)
            if opt_section_match:
                opt_lines = opt_section_match.group(1).strip().split('\n')
                for line in opt_lines:
                    # 兼容选项中的图片
                    img_in_opt = re.findall(r'!\[.*?\]\((.*?)\)', line)
                    # 处理选项文本
                    m = re.match(r'\s*-\s*([A-Ga-g])[ \.．、,，:：](.*)', line)
                    if m:
                        key = m.group(1).lower()
                        val = m.group(2).strip().rstrip('；').rstrip(';').rstrip('。')
                        # 如果选项里有图片，把图片占位符替换
                        if img_in_opt:
                            val = re.sub(r'!\[.*?\]\(.*?\)', '[图片]', val)
                            # 这里原系统可能不支持选项带图片，但我们先记录下来
                        options[key] = val
            
            # 解析答案
            ans_match = re.search(r'-\s+\*\*标准答案\*\*:\s*\*\*([A-Ga-g]+|正确|错误)\*\*', q_block)
            answer = []
            if ans_match:
                raw_ans = ans_match.group(1)
                if type_code == 3: # 判断题
                    if raw_ans in ['A', '正确']:
                        answer = "true"
                    else:
                        answer = "false"
                    options = {} 
                else:
                    answer = [c.lower() for c in raw_ans if c.upper() in 'ABCDEFG']
            
            if not question_text and not q_id:
                continue

            q_obj = {
                "id": q_id if q_id else len(all_questions) + 6000000,
                "type": "单选题" if type_code == 1 else ("多选题" if type_code == 2 else "判断题"),
                "type_code": type_code,
                "question": question_text,
                "question_html": question_text,
                "question_images": question_images,
                "options": options,
                "option_images": {},
                "answer": answer,
                "analysis": ""
            }
            all_questions.append(q_obj)
            type_count += 1
        
        print(f"解析题型 [{type_name}]: {type_count} 题")
            
    return all_questions

if __name__ == "__main__":
    md_file = "/Users/ditto/Documents/jingjipeixun/forklift_study_guide.md"
    output_file = "/Users/ditto/Documents/jingjipeixun/training_system/static/data/junrui.json"
    
    results = parse_md(md_file)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"成功解析 {len(results)} 道题目到 {output_file}")
