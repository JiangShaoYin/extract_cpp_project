#!/usr/local/anaconda3/bin/python3

from asyncio.proactor_events import constants
from operator import is_
import os
import sys
import shutil
import concurrent.futures

def process_file(src_file_path, dest_dir_path):
    os.makedirs(dest_dir_path, exist_ok=True)
    dest_file_path = os.path.join(dest_dir_path, os.path.basename(src_file_path))
    shutil.copy(src_file_path, dest_file_path)


def process_file_multithreaded(filename, src_file_path, dest_dir_path):
    if filename.endswith(".h") or filename.endswith(".cpp"):
        process_file(src_file_path, dest_dir_path)
    else:
        os.makedirs(dest_dir_path, exist_ok=True)
        shutil.copy(src_file_path, dest_dir_path)

def trim_start_blank_line(str):
    end = 0
    while True:
        if end >= len(str):
            break
        if str[end] != ' ' or str[end] != '\t':
            return str
        if str[end] == '\n':
            end += 1
            break
        end += 1

    print(f"end: {end}")
    return str[end:]

def clip_tail_semicolon(content):
    stripped_str = content.replace(" ;", ";")
    return stripped_str

def remove_comment(content):
    if content.startswith("//"):
        end_pos = content.find("\n")
        if len(content) >= end_pos:
            return content[end_pos:]

    if content.startswith("/**"):
        end_str = "*/"
        end_pos = content.find("*/") + len(end_str)

        if len(content) >= end_pos:
            return content[end_pos:]

    return content

def trim(content):
    if content.startswith("...\n"):
        return content[4:]
    if content.startswith("... \n"):
        return content[5:]
    if content.startswith("\n  ... "):
        return content[7:]

    content = remove_comment(content)
    content = trim_start_blank_line(content)
    return content


def skip_line(str, index):
    pre_content = str[:index]
    content = str[index:]
    return pre_content + trim(content)

def clean_class_functions(content):
    result = []
    depth = 0  # 当前大括号深度
    index = 0  # 当前解析的字符位置
    function_depth = None  # 函数定义开始的大括号深度
    last_function_index = None  # 记录最后一个函数定义的位置

    while index < len(content):
        content = skip_line(content, index)
        # print(content)

        if content[index] == '{':
            depth += 1
            if function_depth is None and (content.rfind(';', 0, index) < content.rfind(')', 0, index)):
                # 函数定义开始
                function_depth = depth
                last_function_index = len(result)

        if content[index] == '}':
            if depth == function_depth:
                # 函数结束，移除函数体并保留函数声明
                result = result[:last_function_index] + [';']
                function_depth = None
                last_function_index = None
                index += 1  # 跳过当前的 '}'
                continue  # 跳过当前的 '}'
            depth -= 1

        if function_depth is None or depth < function_depth:
            result.append(content[index])

        index += 1

    res = ''.join(result)
    return res.replace(";}", ";")

def remove_blank_lines_between_functions(content):
    lines = content.split('\n')
    result_lines = []
    pre_line = None
    for line in lines:
        if line == "":
            continue
        result_lines.append(clip_tail_semicolon(line))

    return '\n'.join(result_lines)

def process_file(src_file_path, dest_dir_path):
    with open(src_file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    new_content_with_blank = clean_class_functions(content)
    new_content = remove_blank_lines_between_functions(new_content_with_blank)

    filename = os.path.basename(src_file_path)
    dest_file_path = os.path.join(dest_dir_path, filename)
    os.makedirs(dest_dir_path, exist_ok=True)

    with open(dest_file_path, 'w', encoding='utf-8') as file:
        file.write(new_content)
    print(f"write to: {dest_file_path}")

def process_header_files(path):
    if os.path.isfile(path):
        dst_dir = "./tmp/dst"
        src_dir = "./tmp/src"
        filename = os.path.basename(path)

        src_filename = f"{src_dir}/{filename}"
        if not os.path.exists(src_filename):
            os.makedirs(src_dir, exist_ok=True)
            os.makedirs(dst_dir, exist_ok=True)
            shutil.copy(path, src_dir)

        process_file(src_filename, dst_dir)
        return

    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as executor:
        futures = []
        for root, _, files in os.walk(path):
            for filename in files:
                src_file_path = os.path.join(root, filename)

                if "bazel-" in src_file_path:
                    continue

                if ".git" in src_file_path:
                    continue

                relative_path = os.path.relpath(root, path)
                dest_dir_path = os.path.join(f"processed/{path}", relative_path)

                futures.append(executor.submit(process_file_multithreaded, filename, src_file_path, dest_dir_path))

        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error processing file: {e}")

process_header_files(sys.argv[1])