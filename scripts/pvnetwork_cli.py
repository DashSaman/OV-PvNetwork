#!/usr/bin/env python3
"""PVNetwork operational console: bilingual menus and bounded automation."""
import argparse
import json
import os
import sys

MENU=[
    {'id':number,'command':command,'en':en,'fa':fa}
    for number,(command,en,fa) in enumerate([
        ('status','Dashboard / Status','داشبورد / وضعیت'),
        ('services','Services management','مدیریت سرویس‌ها'),
        ('nodes','Node management','مدیریت نودها'),
        ('sessions','User / Session diagnostics','بررسی کاربران / نشست‌ها'),
        ('logs','System logs','لاگ‌های سیستم'),
        ('troubleshoot','Errors / Troubleshooting','خطاها / عیب‌یابی'),
        ('doctor','Doctor','بررسی سلامت'),
        ('repair','Scoped safe repair','ترمیم ایمن محدود'),
        ('update','Update','به‌روزرسانی'),
        ('backup','Backup','پشتیبان‌گیری'),
        ('restore','Restore','بازیابی'),
        ('rollback','Rollback','بازگشت نسخه'),
        ('tls','SSL / TLS management','مدیریت گواهی TLS'),
        ('settings','Panel URL / Port / Path','نشانی / پورت / مسیر پنل'),
        ('credentials','Administrator credentials','اطلاعات ورود مدیر'),
        ('firewall','Firewall diagnostics','بررسی فایروال'),
        ('network','Network diagnostics','بررسی شبکه'),
        ('nginx','Nginx / Reverse proxy','بررسی پراکسی Nginx'),
        ('database','Database / Migrations','دیتابیس / مهاجرت‌ها'),
        ('resources','System resources','منابع سیستم'),
        ('jobs','Background jobs','کارهای پس‌زمینه'),
        ('version','Version information','اطلاعات نسخه'),
        ('support','Sanitized support bundle','بستهٔ پشتیبانی پاک‌سازی‌شده'),
        ('language','Language settings','تنظیم زبان'),
        ('exit','Exit','خروج'),
    ],1)
]
UNITS=['pvnetwork-panel.service',*[f'pvnetwork-{name}.timer' for name in [
    'usage-sync','sub-push','user-rename-worker','node-user-reconcile','bandwidth-reconcile',
    'panel-monitor','panel-smoke','panel-backup','panel-user-notifier','panel-healthcheck']]]
REPAIR_SCOPES=['panel-service','panel-timers','node-reconcile']


class UsageError(ValueError):pass


class Parser(argparse.ArgumentParser):
    def error(self,message):raise UsageError(message)


def common(parser,*,child=False):
    options={'default':argparse.SUPPRESS} if child else {}
    for flag in ['json','yes','dry-run']:
        parser.add_argument('--'+flag,action='store_true',**options)
    parser.add_argument('--lang',choices=['en','fa'],**({'default':argparse.SUPPRESS} if child else {'default':'fa' if os.getenv('LANG','').startswith('fa') else 'en'}))


def parser():
    root=Parser(prog='pvnetwork',description=__doc__);common(root)
    commands=root.add_subparsers(dest='command')
    for item in MENU[:-1]:
        command=item['command'];child=commands.add_parser(command,help=item['en']);common(child,child=True)
        if command=='services':
            child.add_argument('action',nargs='?',default='status',choices=['status','start','stop','restart','enable','disable'])
            child.add_argument('--unit',choices=UNITS,default='pvnetwork-panel.service')
        elif command=='repair':child.add_argument('--scope',required=True,choices=REPAIR_SCOPES)
        elif command in {'update','restore'}:
            child.add_argument('selection',nargs='?');child.add_argument('--archive');child.add_argument('--sha256')
            if command=='update':child.add_argument('--adopt-rooted',action='store_true')
        elif command=='logs':
            child.add_argument('--unit',choices=UNITS,default='pvnetwork-panel.service');child.add_argument('--lines',type=int,default=80)
        elif command=='nodes':
            child.add_argument('action',nargs='?',default='list',choices=['list','health','deploy','edit','drain','undrain','enable','disable','reconcile','remove','backup','restore','recover','job'])
            child.add_argument('--node-id',type=int);child.add_argument('--job-id');child.add_argument('--input-json-stdin',action='store_true')
        elif command in {'settings','credentials'}:
            child.add_argument('action',nargs='?',default='show',choices=['show','apply']);child.add_argument('--input-json-stdin',action='store_true')
        elif command=='tls':
            child.add_argument('action',nargs='?',default='inspect',choices=['inspect','renew'])
        elif command=='nginx':child.add_argument('action',nargs='?',default='inspect',choices=['inspect','check'])
        elif command=='database':child.add_argument('action',nargs='?',default='inspect',choices=['inspect','check','migrations'])
        elif command=='support':child.add_argument('--output',required=True)
        elif command=='language':
            child.add_argument('action',nargs='?',default='show',choices=['show','set']);child.add_argument('preference',nargs='?',choices=['en','fa'])
        elif command=='sessions':child.add_argument('--user-id')
    # Preserve the existing internal restore worker and lifecycle recovery entry points.
    for command in ['recover','restore-upload']:
        child=commands.add_parser(command);common(child,child=True)
        if command=='restore-upload':child.add_argument('selection');child.add_argument('--archive',required=True)
    return root


def mutation(args):
    command=args.command;action=getattr(args,'action',None)
    return command in {'backup','restore','update','rollback','recover','restore-upload','repair','support'} or (
        command=='services' and action!='status') or (command=='nodes' and action not in {'list','health','job'}) or (
        command in {'settings','credentials'} and action=='apply') or (command=='tls' and action=='renew') or (command=='language' and action=='set')


def plan(args):
    result={'command':args.command}
    for key in ['action','unit','scope','selection','node_id','job_id','output','preference']:
        value=getattr(args,key,None)
        if value is not None:result[key]=value
    result['engine']='native-lifecycle' if args.command in {'backup','restore','update','rollback','recover','restore-upload'} else 'scoped-local-operation'
    return result


def confirm(args,proposal):
    if args.yes:return True
    if not sys.stdin.isatty():return False
    print(json.dumps(proposal,ensure_ascii=False))
    prompt='برای تأیید دقیقاً YES بنویسید: ' if args.lang=='fa' else 'Type YES to confirm this scoped change: '
    try:return input(prompt)=='YES'
    except (EOFError,KeyboardInterrupt):return False


def dispatch(args):
    from pvnetwork_cli_operations import execute
    return execute(args)


def emit(value,args):
    if args.json:print(json.dumps(value,ensure_ascii=False))
    else:
        data=value.get('data',value)
        print(json.dumps(data,ensure_ascii=False,indent=2))


def execute(args):
    if args.command=='logs' and not 1<=args.lines<=500:raise UsageError('--lines must be between 1 and 500')
    if args.command=='nodes' and args.action not in {'list','health','deploy'} and (args.node_id is None or args.node_id<1):raise UsageError('a positive --node-id is required')
    proposal=plan(args)
    if args.dry_run:
        emit({'success':True,'dry_run':True,'plan':proposal},args);return 0
    if mutation(args):
        if os.geteuid()!=0:raise PermissionError('root access is required')
        if args.command not in {'backup','support','language'} and not confirm(args,proposal):raise PermissionError('explicit confirmation required; use --yes for automation')
    result=dispatch(args);emit({'success':True,'data':result},args);return 0


def interactive(args):
    while True:
        print('\nPVNetwork')
        for item in MENU:print(f"{item['id']:2}. {item[args.lang]}")
        try:choice=input('انتخاب: ' if args.lang=='fa' else 'Select: ').strip()
        except (EOFError,KeyboardInterrupt):print();return 0
        if not choice.isdigit() or not 1<=int(choice)<=25:
            print('گزینه نامعتبر است' if args.lang=='fa' else 'Invalid selection');continue
        item=MENU[int(choice)-1]
        if item['command']=='exit':return 0
        if item['command']=='language':
            args.lang='fa' if args.lang=='en' else 'en';continue
        try:
            # Command help exposes the concrete operations before collecting input.
            options=input((item[args.lang]+' — ') + ('آرگومان‌ها (برای راهنما --help): ' if args.lang=='fa' else 'arguments (--help for choices): '))
            import shlex
            command=parser().parse_args(['--lang',args.lang,item['command'],*shlex.split(options)])
            execute(command)
        except SystemExit:pass
        except (UsageError,PermissionError,RuntimeError,OSError,ImportError):
            print('عملیات انجام نشد؛ محدوده، مجوز و راهنما را بررسی کنید.' if args.lang=='fa' else 'Operation did not complete; check scope, permissions and command help.')
        except (EOFError,KeyboardInterrupt):print()


def main(argv=None):
    args=None
    try:
        args=parser().parse_args(argv)
        if not args.command:
            if sys.stdin.isatty():return interactive(args)
            parser().print_help();return 64
        return execute(args)
    except SystemExit as exc:return int(exc.code or 0)
    except UsageError:
        print('[PVNetwork] Invalid command or arguments; use pvnetwork --help',file=sys.stderr);return 64
    except PermissionError:
        print(json.dumps({'success':False,'error':'Permission or explicit confirmation required','code':77}),file=sys.stderr);return 77
    except (RuntimeError,OSError,ImportError,ValueError):
        print(json.dumps({'success':False,'error':'Operation unavailable or failed; inspect private diagnostics','code':69}),file=sys.stderr);return 69
    except KeyboardInterrupt:return 130
    except Exception as exc:
        code=getattr(exc,'code',70)
        if code not in {64,69,70,75,77}:code=70
        print(json.dumps({'success':False,'error':'Operation failed; check the selected scope and private diagnostics','code':code}),file=sys.stderr);return code


if __name__=='__main__':raise SystemExit(main())
