#!/usr/bin/env python
# -*- coding: utf-8 -*-

# @Author  : bianbian
# @Site    : Asia/Shanghai
# @File    : test.py
# @Software: bianbian's PyCharm
# @Time    : 2019/1/17 9:30
import datetime
import os
import random
import time
import math

from utils.log import logger
from utils.date import timestamp

from github import Github
from config.database import result_col, query_col, blacklist_col, notice_col, github_col, setting_col, REDIS_HOST, \
    REDIS_PORT
from pymongo import errors

def run():
    # setting_col.update_one({'key': 'task'}, {'$set': {'key': 'task', 'pid': os.getpid()}}, upsert=True)
    query_count = query_col.count({'enabled': True})
    logger.info('需要处理的关键词总数: {}'.format(query_count))
    if query_count:
        logger.info('需要处理的关键词总数: {}'.format(query_count))
    else:
        logger.warning('请添加关键词')
        return
    if github_col.count({'rate_remaining': {'$gt': 5}}):
        pass
    else:
        logger.error('请配置github账号')
        return

    if setting_col.count({'key': 'task', 'page': {'$exists': True}}):
        setting_col.update_one({'key': 'task'}, {'$set': {'pid': os.getpid()}})
        page = int(setting_col.find_one({'key': 'task'}).get('page'))

        for p in range(0, page):
            for query in query_col.find({'enabled': True}).sort('last', 1):
                github_account = random.choice(
                    list(github_col.find({"rate_limit": {"$gt": 5}}).sort('rate_remaining', -1)))
                github_username = github_account.get('username')
                github_password = github_account.get('password')
                rate_remaining = github_account.get('rate_remaining')
                logger.info(github_username)
                logger.info(rate_remaining)
                g = Github(github_username, github_password,
                           user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.81 Safari/537.36')

                # total = query.get('total')
                # if total is None:
                #     repos = g.search_code(query=query.get('keyword'),
                #                           sort="indexed", order="desc")
                #     total = repos.totalCount
                repos = g.search_code(query=query.get('keyword'),
                                      sort="indexed", order="desc")
                total = repos.totalCount

                page_pre = int(query.get('page_pre')) if query.get('page_pre') is not None else -1
                page_all = math.ceil(total / 30)
                if page_pre + 1 >= page_all:
                    page_pre = -1
                page_now = page_pre + 1
                query_col.update_one({'_id': query.get('_id')},
                                     {'$set': {'total': total, 'page_pre': page_now}})

                search(query, page_now, g, github_username)


    else:
        logger.error('请在页面上配置任务参数')


def search(query, page, g, github_username):
    mail_notice_list = []
    ding_notice_list = []
    logger.info('开始抓取: tag is {} keyword is {}, page is {}'.format(
        query.get('tag'), query.get('keyword'), page + 1))
    try:
        repos = g.search_code(query=query.get('keyword'),
                              sort="indexed", order="desc")
        github_col.update_one({'username': github_username},
                              {'$set': {'rate_remaining': int(g.get_rate_limit().search.remaining)}})

    except Exception as error:
        logger.critical(error)
        logger.critical("触发限制啦")
        return
    try:
        for repo in repos.get_page(page):
            setting_col.update_one({'key': 'task'}, {'$set': {'key': 'task', 'pid': os.getpid(), 'last': timestamp()}},
                                   upsert=True)
            if not result_col.count({'_id': repo.sha}):
                try:
                    code = str(repo.content).replace('\n', '')
                except:
                    code = ''
                leakage = {
                    'link': repo.html_url,
                    'project': repo.repository.full_name,
                    'project_url': repo.repository.html_url,
                    '_id': repo.sha,
                    'language': repo.repository.language,
                    'username': repo.repository.owner.login,
                    'avatar_url': repo.repository.owner.avatar_url,
                    'filepath': repo.path,
                    'filename': repo.name,
                    'security': 0,
                    'ignore': 0,
                    'tag': query.get('tag'),
                    'code': code,
                }
                try:
                    leakage['affect'] = []
                except:
                    logger.critical(leakage.get('link'))
                    leakage['affect'] = []
                if int(repo.raw_headers.get('x-ratelimit-remaining')) == 0:
                    logger.critical('剩余使用次数: {}'.format(
                        repo.raw_headers.get('x-ratelimit-remaining')))
                    return
                last_modified = datetime.datetime.strptime(
                    repo.last_modified, '%a, %d %b %Y %H:%M:%S %Z')
                leakage['datetime'] = last_modified
                leakage['timestamp'] = last_modified.timestamp()
                in_blacklist = False
                for blacklist in blacklist_col.find({}):
                    if blacklist.get('text').lower() in leakage.get('link').lower():
                        logger.warning('{} 包含白名单中的 {}'.format(
                            leakage.get('link'), blacklist.get('text')))
                        in_blacklist = True
                if in_blacklist:
                    continue
                if result_col.count({"project": leakage.get('project'), "ignore": 1}):
                    continue
                if not result_col.count(
                        {"project": leakage.get('project'), "filepath": leakage.get("filepath"), "security": 0}):
                    mail_notice_list.append(
                        '上传时间:{} 地址: <a href={}>{}/{}</a>'.format(leakage.get('datetime'), leakage.get('link'),
                                                                  leakage.get('project'), leakage.get('filename')))
                    ding_notice_list.append(
                        '[{}/{}]({}) 上传于 {}'.format(leakage.get('project').split('.')[-1],
                                                    leakage.get('filename'), leakage.get('link'),
                                                    leakage.get('datetime')))
                try:
                    result_col.insert_one(leakage)
                    logger.info(leakage.get('project'))
                except errors.DuplicateKeyError:
                    logger.info('已存在')

                logger.info('抓取关键字：{} {}'.format(query.get('tag'), leakage.get('link')))
    except Exception as error:
        if 'Not Found' not in error.data:
            # g, github_username = new_github()
            # search.schedule(
            #     args=(query, page, g, github_username),
            #     delay=huey.pending_count() + huey.scheduled_count())
            pass
        logger.critical(error)
        logger.error('抓取: tag is {} keyword is {}, page is {} 失败'.format(
            query.get('tag'), query.get('keyword'), page + 1))

        return
    logger.info('抓取: tag is {} keyword is {}, page is {} 成功'.format(
        query.get('tag'), query.get('keyword'), page + 1))
    query_col.update_one({'tag': query.get('tag')},
                         {'$set': {'last': int(time.time()), 'status': 1, 'reason': '抓取第{}页成功'.format(page),
                                   'api_total': repos.totalCount,
                                   'found_total': result_col.count({'tag': query.get('tag')})}})
    # if setting_col.count({'key': 'mail', 'enabled': True}) and len(mail_notice_list):
    #     main_content = '<h2>规则名称: {}</h2><br>{}'.format(query.get('tag'), '<br>'.join(mail_notice_list))
    #     send_mail(main_content)
    # logger.info(len(ding_notice_list))
    # if setting_col.count({'key': 'dingtalk', 'enabled': True}) and len(ding_notice_list):
    #     dingtalk(query.get('tag'), ding_notice_list)



if __name__ == '__main__':
    run()
    print(1234)
