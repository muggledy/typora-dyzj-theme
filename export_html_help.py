import re, os
import datetime
import shutil
from contextlib import contextmanager
import argparse
import hashlib

'''
1. export demo.html of markdown in typora editor.
2. exec `python export_html_help.py demo.html`, this will generate a directory named .temp/ to store resources referenced by the html page,
   this script aims to correct error in missing image notiation.
'''

cur_dir = os.getcwd() #os.path.dirname(os.path.realpath(__file__))
img_wrapper_js = '''<script>Array.from(document.getElementsByTagName("img")).forEach(function(item,index,array){var dyimgdad=item.parentElement;if(dyimgdad.tagName=="P"){var index=[].indexOf.call(dyimgdad.childNodes,item);dyimgdad.removeChild(item);var dyspan=document.createElement("span");dyspan.classList.add("md-image");dyspan.setAttribute("alt",item.getAttribute("alt")?".  "+(/^(shadow-|blur-|gray-)?(.*)$/.exec(item.getAttribute("alt"))[2]):"");dyspan.appendChild(item);index==dyimgdad.childNodes.length?dyimgdad.appendChild(dyspan):dyimgdad.insertBefore(dyspan,Array.from(dyimgdad.childNodes).filter(function(v,k){return k==index})[0])}})</script>'''
get_cur_time = lambda : datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d %H:%M:%S')
basename = lambda path : os.path.basename(path.replace('\\', os.sep).replace('/', os.sep))
convert_raw_pattern = lambda pattern : ''.join([f'\\{c}' if c in r'.^$*+?\[]|{}()' else c for c in pattern])

class Error(Exception):
    def __init__(self, message, err_type):
        self.message = message
        self.err_type = err_type
    def __str__(self):
        return f'[error] {self.message}'

def contrast_file(src_f, dst_f):
    def calc_md5(fpath):
        with open(fpath, 'rb') as f:
            md5obj = hashlib.md5()
            md5obj.update(f.read())
            hash = md5obj.hexdigest()
        return hash
    return calc_md5(src_f) == calc_md5(dst_f)

def parse_html_cp_file(html_str, dst_dir):
    pattern_file = re.compile(r'file:///(.*?)[\'"\)]')
    for _full_path in set(pattern_file.findall(html_str)):
        full_path = os.path.normpath(re.findall(r'^([^\?]*)[\?]?', _full_path)[0])
        if not os.path.exists(full_path):
            print(f'[{get_cur_time()}] [warn] Resource file {full_path} not exist!')
            continue
        for fpath in os.listdir(dst_dir):
            dst_fpath = os.path.join(dst_dir, fpath)
            if contrast_file(full_path, dst_fpath) == True:
                print('[%s] (no cp) %s == %s' % (get_cur_time(), full_path, dst_fpath))
                break
        else:
            fpath = f'{basename(full_path)}'
            cp_fpath = os.path.join(dst_dir, fpath)
            if os.path.exists(cp_fpath):
                fpath  = f'{datetime.datetime.now().timestamp()}_{fpath}'
                cp_fpath = os.path.join(dst_dir, fpath)
            shutil.copyfile(full_path, cp_fpath)
            print('[%s] cp %s -> %s' % (get_cur_time(), full_path, cp_fpath))
        yield f'file:///{_full_path}'.encode('unicode_escape').decode(), os.path.join(f'./{basename(dst_dir)}/', fpath)

def fix_bug_of_a_img(html_str):
    p1 = re.compile(r'(([ \r\n]*(<a[^<>]*?alt *= *[\'"]null[\'"] *>([^<>]*?<img[^<>]*?>[^<>]*?)+?</a>)[ \r\n]*)+)')
    p2 = re.compile(r'(<[^<>]+>)')
    p3 = re.compile(r'<img[^<>]+>')
    def delete_space(match):
        s = match.group(0)
        s = ''.join(p2.findall(s))
        return p3.sub('\g<0> ', s)
    html_str = p1.sub(delete_space, html_str)
    return html_str

def fix_html(context):
    pattern_wrapper = re.compile(convert_raw_pattern(img_wrapper_js))
    with open(context['filename'], 'r', encoding = 'utf-8') as f:
        html = f.read()
        if html == '':
            print(f'[{get_cur_time()}] [error] {context["filename"]} is null!')
            return
        if pattern_wrapper.findall(html):
            print(f'[{get_cur_time()}] [ok] {context["filename"]} is already processed!')
            return
    html = fix_bug_of_a_img(html)
    with open(context['filename'], 'w', encoding = 'utf-8') as f:
        html = re.sub(r'(</html>)$', f'{img_wrapper_js}\n\g<0>', html)
        print('[%s] Inject img_wrapper_js into %s' % (get_cur_time(), context['filename']))
        for _old_p, new_p in parse_html_cp_file(html, dst_dir = context['tmp_dir']):
            old_p = convert_raw_pattern(_old_p)
            if not re.findall(old_p, html):
                raise Error(f'Match {_old_p} failed in {context["filename"]}!', 1)
            html = re.sub(old_p, new_p, html)
        f.write(html)
    print(f'[{get_cur_time()}] [ok] {context["filename"]} converted success!')

def print_directory(path, show_file = True, show_relative = False):
    print(' [D] ' + path + '\\')
    def recursion_print(path, depth = 1):
        for eachFile in os.listdir(path):
            each_filePath = os.path.join(path, eachFile)
            if os.path.isdir(each_filePath):
                print('    ' * depth + ' [D] ' + (each_filePath if not show_relative else eachFile) + '\\')
                recursion_print(each_filePath, depth = depth + 1)
            else:
                if show_file:
                    print('    ' * depth + ' [F] ' + (each_filePath if not show_relative else eachFile))
    recursion_print(path)

@contextmanager
def process_html(filename, **kwargs):
    context = {}
    filename = filename if os.path.isabs(filename) else os.path.join(cur_dir, filename)
    context['filename'] = filename
    process_dir = os.path.dirname(filename)
    context['tmp_dir'] = os.path.normpath(os.path.join(process_dir, kwargs.get('output', '.temp')))
    _ = context['tmp_dir']
    print('[%s] %s' % (get_cur_time(), f'Create directory {_}' if not os.path.exists(_) else f'{_} exists'))
    os.makedirs(context['tmp_dir'], exist_ok = True)
    try:
        yield context
    except Exception as e:
        print(f'[{get_cur_time()}] {e}')
        if e.args[1] == 0 and not os.listdir(context["tmp_dir"]):
            del_temp = 'y'
        else:
            del_temp = input(f'[{get_cur_time()}] [warn] Are you sure to delete directory {context["tmp_dir"]}? [y/n] ')
        if del_temp != '' and del_temp in 'yY':
            shutil.rmtree(context["tmp_dir"])
            print(f'[{get_cur_time()}] Delete {context["tmp_dir"]} directory')
    if kwargs.get('print_dir', None):
        print_directory(process_dir, True, True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog = 'python export_html_help.py', description = 'The html-format export assistant of typora.')
    parser.add_argument('files', nargs = '*', help = 'arbitrary .html files or dir(default is current work dir. process all .html in it) to be procesed')
    parser.add_argument('--output', type = str, default = ".temp", help = "the directory name where you want to copy file:// to")
    parser.add_argument('-p', '--print_dir', action='store_true', help='print the file tree of processed dir(default is False)')
    args = parser.parse_args()
    args.files = [cur_dir, *(args.files)] if args.files == [] else args.files
    all_files = []
    [all_files.append(_) if not os.path.isdir(_) else all_files.extend([os.path.join(_, i) for i in os.listdir(_) if os.path.splitext(i)[1] == '.html']) for _ in args.files]
    all_files = set([os.path.normpath(_) if os.path.isabs(_) else os.path.normpath(os.path.join(cur_dir, _)) for _ in all_files])
    for html_file in all_files:
        with process_html(html_file, print_dir = args.print_dir, output = args.output) as context:
            if not os.path.exists(context['filename']):
                raise Error(f'File {context["filename"]} not exists!', 0)
            fix_html(context)
