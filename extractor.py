#!/usr/local/anaconda3/bin/python3

from asyncio.proactor_events import _ProactorDuplexPipeTransport, constants
from operator import is_
import os
import re
import sys
import shutil
import concurrent.futures
from webbrowser import get
import subprocess

MAX_CHAR_BEFORE_COMMENT = 15
MAX_TEMPLATE_HEAD_LEN = 128

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


def clip_tail_semicolon(content):
    stripped_str = content.replace(" ;", ";")
    return stripped_str


def get_comment_start_pos(content, comment_begin_str):
    return content[:MAX_CHAR_BEFORE_COMMENT].find(comment_begin_str)

def is_empty_str(content):
    for char in content:
        if char != ' ' and char != '\t' and char != '\n':
            return False

    return True

# /n      //
# /n      /**
def is_next_line_start_comment(content):
    if not content.startswith("\n"):
        return False

    next_CRLF_pos = 1 + content[1:].find("\n")

    comment = content[1 : next_CRLF_pos]

    pos1 = get_comment_start_pos(comment, "//")
    pos2 = get_comment_start_pos(comment, "/**")

    if pos1 == -1 and pos2 == -1:
        return False

    # here the content is definitely a comment, we want to ensure
    if pos1 >= 0:
        pos = pos1

    if pos2 >= 0:
        pos = pos2

    if pos1 >= 0 and pos2 >= 0:
        pos = min(pos1, pos2) + 1 # include the first \n character

    return is_empty_str(content[1 : pos])

# including blank characters
def is_start_with(content, target):
    pos = content.find(target)
    if pos == -1:
        return False
    for c in content[:pos]:
        if c != ' ' and c != '\t':
            return False
    return True

def remove_comment(content):
    if is_start_with(content, "//"):
        end_pos = content.find("\n")
        if len(content) >= end_pos:
            return content[end_pos:]

    if is_start_with(content, "/**"):
        end_str = "*/"
        end_pos = content.find("*/") + len(end_str)

        if len(content) >= end_pos:
            return content[end_pos:]

    return content



def align_str_in_bracket(content):
    if not content.startswith("("):
        return content

    right_bracket_pos = content.find(")")

    sub_str = content[:right_bracket_pos + 1]
    sub_str = sub_str.replace('\n', '')

    items = sub_str.split(" ")
    result = [item for item in items if item != '']

    return " ".join(result) + content[right_bracket_pos + 1:]


def align_template_function(content):
    if not content.startswith("template <"):
        return content

    cur_CRLF_pos = content[:MAX_TEMPLATE_HEAD_LEN].find("\n")
    next_CRLF_pos = cur_CRLF_pos + 1 + content[cur_CRLF_pos + 1:].find("\n")
    function_str = content[cur_CRLF_pos + 1:next_CRLF_pos]

    if "(" not in function_str or ")" not in function_str:
        return content

    function_start_pos = 0
    for c in function_str:
        if c == ' ' or c == '\t':
            function_start_pos += 1
            continue
        break

    stripped_function_str = function_str[function_start_pos:]

    return content[:cur_CRLF_pos] + " " + stripped_function_str + content[next_CRLF_pos:]


# core function
def trim(content):
    content = remove_comment(content)
    content = align_template_function(content)
    content = align_str_in_bracket(content)
    return content


def trim_line(str, index):
    content = str[index:]

    trimmed = trim(content)
    if trimmed == content:
        return str, False

    pre_content = str[:index]
    return pre_content + trimmed, True


def clean_class_functions(content):
    result = []
    depth = 0  # 当前大括号深度
    index = 0  # 当前解析的字符位置
    function_depth = None  # 函数定义开始的大括号深度
    last_function_index = None  # 记录最后一个函数定义的位置

    while index < len(content):
        content, is_trimmed = trim_line(content, index)
        # if is_trimmed:
        #     continue

        if content[index] == '{':
            depth += 1
            if function_depth is None and (content.rfind(';', 0, index) < content.rfind(')', 0, index)):
                # 函数定义开始
                function_depth = depth
                last_function_index = len(result)

        if content[index] == '}':
            if depth == function_depth:
                last_char = result[last_function_index - 1]

                if last_char == ' ':
                    result = result[:last_function_index - 1] + [';']
                else:
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

def run(path):
    if os.path.isfile(path):
        dst_dir = "./tmp/dst"
        src_dir = "./tmp/src"
        filename = os.path.basename(path)

        src_filename = f"{src_dir}/{filename}"
        if not os.path.exists(src_filename):
            os.makedirs(src_dir, exist_ok=True)
            os.makedirs(dst_dir, exist_ok=True)
            # shutil.copy(path, src_dir)
        subprocess.call(['cp', path, src_dir])

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

run(sys.argv[1])