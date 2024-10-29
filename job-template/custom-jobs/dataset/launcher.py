
import os,sys
import argparse
import datetime
import json
import time
from multiprocessing import Pool
from functools import partial
import uuid
import pysnooper
import re
import requests
import copy
import os
import shutil
KFJ_CREATOR = os.getenv('KFJ_CREATOR', 'admin')
KFJ_TASK_PROJECT_NAME = os.getenv('KFJ_TASK_PROJECT_NAME','public')

host = os.getenv('HOST',os.getenv('KFJ_MODEL_REPO_API_URL','http://kubeflow-dashboard.infra')).strip('/')

# @pysnooper.snoop()
def download_file(url, des_dir=None, overwrite='True'):
    if des_dir:
        local_path = os.path.join(des_dir, url.split('/')[-1])
        

    if url.startswith('/label-studio'):
        if not os.path.exists(local_path):
            os.mkdir(local_path)
        for root, dirs, files in os.walk(url):
            for file in files:
                src_file = os.path.join(url, file)
                dest_file = os.path.join(local_path, file)
                if  overwrite == 'False' and os.path.exists(dest_file):
                    print(dest_file, ' 已经存在')
                    continue
                shutil.copy2(src_file, dest_file)
        return
    
    print(f'begin donwload {local_path} from {url}')
    if not os.path.exists(des_dir):
        os.mkdir(des_dir)
    # 注意传入参数 stream=True
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        total_length = int(r.headers['content-length'])
        chunk_size=102400
        count = 0
        import time
        t = time.time()
        if os.path.isfile(local_path):
            if  overwrite == 'False':
                print(local_path,'已经存在')
                return
            else:
                os.remove(local_path)
        with open(local_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size):
                f.write(chunk)
                count += 1
                p = count * chunk_size * 100 / total_length
                if p > 100:
                    p = 100
                if time.time() - t > 5:
                    print('downloading ', round(p,2),'%')
                    t = time.time()
        r.close()

# @pysnooper.snoop()
def download(name,version,save_dir,overwrite,**kwargs):
    print('name ', name)
    print('version: ', version)
    print('save_dir: ', save_dir)
    print(kwargs)
    print(KFJ_CREATOR)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': KFJ_CREATOR
    }

    # 获取项目组, 查询是否存在，创建者是不是指定用户
    url = host + "/dataset_modelview/api/?form_data=" + json.dumps({
        "filters": [
            {
                "col": "name",
                "opr": "eq",
                "value":name
            },
            {
                "col": "version",
                "opr": "eq",
                "value": version
            }
        ]
    })
    res = requests.get(url, headers=headers)
    exist_dataset = res.json().get('result', {}).get('data', [])
    if not exist_dataset:
        print('不存在数据集')
        exit(1)
    exist_dataset = exist_dataset[0]


    # print(exist_dataset)
    
    url = host+f"/dataset_modelview/api/download/{exist_dataset['id']}"
    res = requests.get(url,headers=headers, allow_redirects=False)
    # print(res.json())
    if res.status_code==200:
        result = res.json().get("result", {})
        if result == '':
            print('exit') 
            exit(0)
        donwload_urls = result.get("download_urls", [])
        print(donwload_urls)

        os.makedirs(save_dir, exist_ok=True)
        pool = Pool(len(donwload_urls))  # 开辟包含指定数目线程的线程池
        pool.map(partial(download_file, des_dir=save_dir, overwrite=overwrite), donwload_urls)  # 当前worker，只处理分配给当前worker的任务
        pool.close()
        pool.join()
        # download_file(donwload_urls[0],save_dir)
        exit(0)

    # path = exist_dataset.get('path', {})
    # if path:
    #     path = path.strip().split('\n')[0]
    # if path:
    #     os.
    # print('path',path)
    exit(1)


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser("download dataset launcher")
    arg_parser.add_argument('--src_type', type=str, help="数据集来源", default='当前平台')
    arg_parser.add_argument('--name', type=str, help="数据集名称", default='luna')
    arg_parser.add_argument('--version', type=str, help="数据集版本", default='latest')
    # # arg_parser.add_argument('--partition', type=str, help="数据集分区", default='')
    arg_parser.add_argument('--save_dir', type=str, help="保存目录", default='/mnt/admin/pipeline/example/dataset/')
    arg_parser.add_argument('--overwrite', type=str, help='是否覆盖同名文件', default='True')

    args = arg_parser.parse_args()
    if not args.save_dir:
        args.save_dir = f'/mnt/{KFJ_CREATOR}/dataset/{args.name}/{args.version}'
        # if args.partition:
        #     args.save_dir=f'/mnt/{KFJ_CREATOR}/dataset/{args.name}/{args.version}/{args.partition}'
    # # print("{} args: {}".format(__file__, args))
    # print('args: ', **args.__dict__)
    if args.src_type=='当前平台':
        download(**args.__dict__)
    # elif args.src_type=='huggingface':
    #     pass
    # elif args.src_type=='modelscope':
    #     pass
    # download('luna', 'latest','/mnt')
