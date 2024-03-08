import pickle
import time
from datetime import datetime
from common.log import logger
from os.path import exists
from config import Config
import json

class UserTYPE:
    ROOT_ADMIN = 0
    ADMIN = 1
    USER = 2
    IGNORE_USER = 3

class DefaultKeywordsAndReply:
    default_keywords = ["bot","@bot","gpt","小费","费总","费哥","Felix","felix"]
    default_text_reply_prefix = "好的，我想想 \n"
    default_text_reply_suffix = ""


class UserAccount:
    id = ""
    nick_name = ""

    keywords = {}

    permission = {"语音":False,"语音回复": False,"图片":False,"画图":False,"文件":False,"链接":False,"视频":False,"拍一拍":False}

    voice_reply_prefix = "---收到语音消息，识别中---\n"
    voice_reply_suffix = "\n---回复语音消息结束---"

    image_reply_prefix = "---收到图片消息，识别中---\n"
    image_reply_suffix = "\n---回复图片消息结束---"

    file_reply_prefix = "---收到文件消息，识别中---\n"
    file_reply_suffix = "\n---回复文件消息结束---"

    sharing_reply_prefix = "---收到链接消息，识别中---\n"
    sharing_reply_suffix = "\n---回复链接消息结束---"

    video_reply_prefix = "---收到视频消息，识别中---\n"
    video_reply_suffix = "\n---回复视频消息结束---"

    patpat_reply_prefix = "拍一拍"
    patpat_reply_suffix = "拍拍"

    expire_time = datetime.now()

    is_new_user = True
    user_type = UserTYPE.USER

    def __init__(self, id, nick_name, expire_time_in_seconds,usertype=UserTYPE.USER):
        self.id = id
        self.nick_name = nick_name
        self.expire_time = datetime.fromtimestamp(datetime.now().timestamp()+expire_time_in_seconds)
        self.is_new_user = True
        self.user_type = usertype

    def get_expired_time(self):
        if self.user_type in [UserTYPE.ROOT_ADMIN,UserTYPE.ADMIN]:
            return "永久"
        time_remain = self.expire_time.timestamp()-datetime.now().timestamp()
        logger.info(f'{time_remain} {self.expire_time.timestamp()}')
        if time_remain < 0:
            return "已经过期"
        return f'{time_remain//86400:.0f}天{time_remain%86400//3600:.0f}小时{(time_remain%3600 // 60):.0f}分钟{time_remain%60:.0f}秒'
        
    def is_expired(self):
        if self.user_type in [UserTYPE.ROOT_ADMIN,UserTYPE.ADMIN]:
            return False, "Root" if self.user_type==UserTYPE.ROOT_ADMIN else ""+ "管理员用户，永久使用"
        expired = datetime.now().timestamp() > self.expire_time.timestamp()
        if expired:
            return expired, f'会员{self.nick_name} 使用时间已经结束，请充值继续使用服务'
        else:
            return expired,f"会员{self.nick_name} 使用时间还剩余{self.get_expired_time()}，可充值延长服务时间"

    def get_keywords(self):
        if self.keywords and len(self.keywords)>0:
            ks = list(self.keywords.keys())
            ks.append(DefaultKeywordsAndReply.default_keywords)
            logger.info(f"{self.nick_name} 关键词 {ks}")
            return ks
        return DefaultKeywordsAndReply.default_keywords

    def add_keyword(self, keyword, reply_prefix,reply_suffix):
        self.keywords[keyword] = (reply_prefix, reply_suffix)
    
    def remove_keyword(self,keyword):
        if keyword in self.keywords:
            self.keywords.pop(keyword)
            return True
        return False

    def get_reply_prefix(self, keyword):
        if keyword in self.keywords:
            return self.keywords[keyword][0]
        elif keyword in DefaultKeywordsAndReply.default_keywords:
            return DefaultKeywordsAndReply.default_text_reply_prefix
        return ""
    def get_reply_suffix(self, keyword):
        if keyword in self.keywords:
            return self.keywords[keyword][1]
        elif keyword in DefaultKeywordsAndReply.default_keywords:
            return DefaultKeywordsAndReply.default_text_reply_suffix
        return ""
    
    def get_valid_type(self,type):
        return self.permission[type]

    def set_valid_type(self,type, value):
        self.permission[type] = True if value == '开' else False
        
    def get_allow_types(self):
        allow_types = ""
        for index,type in enumerate(self.permission):
            allow_types+=f"{index} {'开' if self.permission[type] else '关'} {type}\n"
        return allow_types
    
    def update_expire_time(self, months,days,hours):
        logger.info(f'延期用户 {self.nick_name} {months}月{days}日{hours}小时')
        self.expire_time = datetime.fromtimestamp(datetime.now().timestamp()+2592000*months+86400*days+3600*hours)
        
    def __str__(self):
        return f"ID: {self.id}, 昵称: {self.nick_name}, 到期时间: {self.expire_time}, 是否过期: {self.is_expired()[1]}\n关键词: {self.keywords}\n{self.get_allow_types()}"

    def get_user_type(self):
        typestr = "新增" if self.is_new_user else ""
        typestr+= "Root管理员" if self.user_type == UserTYPE.ROOT_ADMIN else ""
        typestr+= "管理员" if self.user_type == UserTYPE.ADMIN else ""
        typestr+= "忽略" if self.user_type == UserTYPE.IGNORE_USER else ""
        typestr+= "用户"
        return typestr
    
available_setting = {
    "save_path": "./useraccount/accounts.pkl",
    "default_permission": {
        "语音":     False,
        "语音回复": False,
        "图片":     False,
        "画图":     False,
        "文件":     False,
        "链接":     False,
        "视频":     False,
        "拍一拍":   False
    },
    "new_user_trial_time":3600,

    "default_keywords":["bot","@bot","gpt",
                        "小费","费总","费哥",
                        "Felix","felix",
                        "哥哥","小助手"],

    "default_text_reply_prefix":"好的，我想想 \n",
    "default_text_reply_suffix":"",
    "default_voice_reply_prefix":"---收到语音消息，识别中---\n",
    "default_voice_reply_suffix":"\n---回复语音消息结束---",

    "default_image_reply_prefix":"---收到图片消息，识别中---\n",
    "default_image_reply_suffix" : "\n---回复图片消息结束---",

    "default_file_reply_prefix" : "---收到文件消息，识别中---\n",
    "default_file_reply_suffix":"\n---回复文件消息结束---",

    "default_sharing_reply_prefix": "---收到链接消息，识别中---\n",
    "default_sharing_reply_suffix" :"\n---回复链接消息结束---",

    "default_video_reply_prefix" : "---收到视频消息，识别中---\n",
    "default_video_reply_suffix" : "\n---回复视频消息结束---",

    "default_patpat_reply_prefix" : "拍一拍",
    "default_patpat_reply_suffix" : "拍拍",

    "commands":{
        "关键词": "kw",
        "延期": "yq",
        "权限": "qx",
        "充值": "cz",
        "查询": "cx",
        "用户列表": "lb",
        "查询设置": "sz",
        "设置": "st",
        "管理": "gl",
        "帮助": "hp",
        "保存": "sv",
        "到期时间": "ddl"
    },

    "root_admins": ["Felix"],
    "user_admins": [],
    "ignore_users":[],

    "auto_welcome_new_user":True,
    "welcome_msg": "欢迎与我聊天, 我不在的时候会有AI小助手和你聊天, 请以小费或者Felix开头, 可以召唤我的AI小助手, 也可以发送 帮助 或者 ?hp 查看说明。",

    "voice_not_allowed_reply": "您尚未开通自动语音识别功能, 可以咨询小助手开通语音识别及语音回复服务",
    "voice_reply_not_allowed": "您尚未开通自动合成语音回复功能, 可以咨询小助手开通自动合成语音回复服务",
    "image_not_allowed_reply": "您尚未开通自动图片理解功能, 可以咨询小助手开通图片理解服务",
    "file_not_allowed_reply": "您尚未开通自动文件理解功能, 可以咨询小助手开通文件理解服务",
    "sharing_not_allowed_reply": "您尚未开通自动网页总结功能, 可以咨询小助手开通网页总结服务",
    "video_not_allowed_reply": "您尚未开通自动视频总结功能, 可以咨询小助手开通视频总结服务",
    "patpat_not_allowed_reply": "您尚未开通拍一拍自动回复功能, 可以咨询小助手开通拍一拍自动回复服务",

    "help_general_user":"##########################\n#\t\t\t  帮助文档\t\t\t\t#\n##########################\n控制命令使用说明，控制命令按照如下格式组成:\n\t命令词 参数\n中间使用空格分隔\n\n命令词：可以使用中文或者以?开头的英文缩写, 可以在每个命令的标题看到对应的命令中文名和英文缩写\n\n参数：可用参数详见每个命令，通常每个参数可以同时使用中文名称或者参数编号，如 关键词设置中，参数列表为 ?(查询), +(添加), -(删除) ,x(清除),  要查询关键词, 即 关键词 ? 或者\n?kw ?\n要添加关键词, 即 ?kw + hi 你好 再见\n要删除关键词, 即 ?kw - hi\n要清除所有关键词, 即 ?kw x",
    "help_general_admin":"控制命令使用说明，控制命令按照如下格式组成:\n命令词 用户 参数\n中间使用空格分隔\n命令词：可以使用中文或者以?开头的英文缩写, 可以在每个命令的标题看到对应的命令中文名和英文缩写\n\n用户：表示针对某个用户进行操作，使用该用户本人昵称或者通过 用户列表 ?lb 命令查询用户的编号，（编号以#开头，只需要输入数字部分即可），某些命令如 关键词 可以省略用户，表示对本人的关键词进行操作\n\n参数：可用参数详见每个命令，通常每个参数可以同时使用中文名称或者参数编号，如 查询命令中，参数列表为 1.关键词，2.权限，3.到期时间，要查询权限，可以使用编号2，即 查询 用户昵称 2",
    "help_keyword_self":"-----------关键词 ?kw-----------\n参数：?|+|-|x\n查询|添加|删除|清除 本人特殊关键词",
    "help_keyword_admin":"-----------关键词 ?kw-----------\n参数：用户 + 关键词 前缀 后缀\n\t\t- 关键词\n\t\t\tx\n例：?kw Felix + hi 你好 再见\n\t表示给Felix添加关键词“hi”, \n\t回复前缀为“你好”, \n\t回复后缀为“再见”\n\n\t?kw Felix - hi\n\t表示删除Felix的关键词“hi”\n\n\t?kw Felix x\n\t表示清除Felix的所有关键词",
    "help_delay":"-----------延期 ?yq-------------\n参数：用户 M(月) D(日) H(时)\n例: ?yq Felix 1 0 0 \n\t表示给Felix延期1个月(30天)\n\n\t?yq Felix 0 7 0\n\t表示给Felix延期7天",
    "help_permission":"-----------权限 ?qx-------------\n参数：用户 类型 开/1|关/0\n例: ?qx Felix 语音 1 \n\t表示允许Felix识别语音消息, 类型包括:\n1.语音, 2.语音回复, 3.图片, 4.画图, 5.文件, 6.链接, 7.视频, 8.拍一拍",
    "help_recharge":"-----------充值 ?cz-------------\n参数：用户 X(天)\n例：?cz Felix 30\n\t表示给Felix充值30天",
    "help_query":"-----------查询 ?cx-------------\n参数：用户 1/关键词 \n\t\t2/权限\n\t\t3/到期时间\n例: ?cx Felix 权限 \n或 ?cx Felix 2\n\t表示查询Felix的权限",
    "help_userlist":"-----------用户列表 ?lb---------\n显示所有用户信息",
    "help_query_setting":"-----------查询设置 ?sz---------\n显示所有设置",
    "help_setting":"-----------设置 ?st-------------\n参数 选项 值\n设置选项的值\n选项: 1/试用时长 X(秒)",
    "help_manage":"-----------管理 ?gl-------------\n参数 用户 管理员|0\n\t昵称 普通 用户|1\n\t昵称 忽略用户|2\n设置用户属性",
    "help_help":"-----------帮助 ?hp-------------\n显示本帮助信息",
    "help_save":"-----------保存 ?sv-------------\n保存当前用户信息",
    "help_ai_reply":"--------------小助手 ?ai-------------\n无参数，切换是否使用AI小助手自动回复消息",
    "help_deadline":"-----------到期时间 ?ddl-------------\n查询到期时间"
}

class UserAccountMgrConfig(dict):
    def __init__(self, d=None):
        super().__init__()
        if d is None:
            d = {}
        for k, v in d.items():
            self[k] = v

    def __getitem__(self, key):
        if key not in available_setting:
            raise Exception("key {} not in available_setting".format(key))
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        if key not in available_setting:
            raise Exception("key {} not in available_setting".format(key))
        return super().__setitem__(key, value)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError as e:
            return default
        except Exception as e:
            raise e


class UserAccountMgr:
    accounts = {}
    save_path = "./useraccount/accounts.pkl"
    commands = {}
    command_list = []
    root_admins = ["Felix"]
    user_admins = []
    ignore_users = []

    auto_welcome_new_user = True
    welcome_msg = ""

    voice_not_allowed_reply = ""
    voice_reply_not_allowed = ""
    image_not_allowed_reply = ""
    file_not_allowed_reply = ""
    sharing_not_allowed_reply = ""
    video_not_allowed_reply = ""
    patpat_not_allowed_reply = ""

    root_admin_help_msg = ""
    admin_help_msg = ""
    user_help_msg = ""

    default_permission ={}
    
    help_general_admin = ""
    help_general_user = ""
    new_user_trial_time = 3600


    def __init__(self):
        self.accounts = {}
        self.load_config()

    def load_config(self):
        config_path = "./useraccount/config.json"
        if not exists(config_path):
            logger.info("配置文件不存在，将使用config-template.json模板")
            config_path = "./useraccount/config-template.json"

        with open(config_path, mode="r", encoding="utf-8") as f:
            config_str= f.read()
        
        # logger.debug(f"[INIT] user account mgr config str: {config_str}")

        # 将json字符串反序列化为dict类型
        config = UserAccountMgrConfig(json.loads(config_str))

        logger.info(f"[INIT] load user account mgr config: {config}")
        self.save_path = config.get("save_path", "./useraccount/accounts.pkl")
        self.new_user_trial_time = config.get("new_user_trial_time", 3600)

        DefaultKeywordsAndReply.default_keywords = config.get("default_keywords", ["bot","@bot","gpt","小费","费总","费哥","Felix","felix","哥哥","宝宝","主人"])
        DefaultKeywordsAndReply.default_text_reply_prefix = config.get("default_text_reply_prefix", "好的，我想想 \n")
        DefaultKeywordsAndReply.default_text_reply_suffix = config.get("default_text_reply_suffix", "")
        self.default_text_reply_prefix = config.get("default_text_reply_prefix", "好的，我想想 \n")
        self.default_text_reply_suffix = config.get("default_text_reply_suffix", "")
        self.default_voice_reply_prefix = config.get("default_voice_reply_prefix", "---收到语音消息，识别中---\n")
        self.default_voice_reply_suffix = config.get("default_voice_reply_suffix", "\n---回复语音消息结束---")
        self.default_image_reply_prefix = config.get("default_image_reply_prefix", "---收到图片消息，识别中---\n")
        self.default_image_reply_suffix = config.get("default_image_reply_suffix", "\n---回复图片消息结束---")
        self.default_file_reply_prefix = config.get("default_file_reply_prefix", "---收到文件消息，识别中---\n")
        self.default_file_reply_suffix = config.get("default_file_reply_suffix", "\n---回复文件消息结束---")
        self.default_sharing_reply_prefix = config.get("default_sharing_reply_prefix", "---收到链接消息，识别中---\n")
        self.default_sharing_reply_suffix = config.get("default_sharing_reply_suffix", "\n---回复链接消息结束---")
        self.default_video_reply_prefix = config.get("default_video_reply_prefix", "---收到视频消息，识别中---\n")
        self.default_video_reply_suffix = config.get("default_video_reply_suffix", "\n---回复视频消息结束---")
        self.default_patpat_reply_prefix = config.get("default_patpat_reply_prefix", "拍一拍")
        self.default_patpat_reply_suffix = config.get("default_patpat_reply_suffix", "拍拍")
        
        self.default_permission = config.get("default_permission", {"语音":False,"语音回复": False,"图片":False,"画图":False,"文件":False,"链接":False,"视频":False,"拍一拍":False})
        self.allow_list = list(self.default_permission.keys())

        self.auto_welcome_new_user = config.get("auto_welcome_new_user", True)
        self.welcome_msg = config.get("welcome_msg", "欢迎与我聊天, 我不在的时候会有AI小助手和你聊天, 请以小费或者Felix开头, 可以召唤我的AI小助手, 也可以发送 帮助 或者 ?hp 查看说明。")
        self.voice_not_allowed_reply = config.get("voice_not_allowed_reply", "您尚未开通自动语音识别功能, 可以咨询小助手开通语音识别及语音回复服务")
        self.voice_reply_not_allowed = config.get("voice_reply_not_allowed", "您尚未开通自动合成语音回复功能, 可以咨询小助手开通自动合成语音回复服务")
        self.image_not_allowed_reply = config.get("image_not_allowed_reply", "您尚未开通自动图片理解功能, 可以咨询小助手开通图片理解服务")
        self.file_not_allowed_reply = config.get("file_not_allowed_reply", "您尚未开通自动文件理解功能, 可以咨询小助手开通文件理解服务")
        self.sharing_not_allowed_reply = config.get("sharing_not_allowed_reply", "您尚未开通自动网页总结功能, 可以咨询小助手开通网页总结服务")
        self.video_not_allowed_reply = config.get("video_not_allowed_reply", "您尚未开通自动视频总结功能, 可以咨询小助手开通视频总结服务")
        self.patpat_not_allowed_reply = config.get("patpat_not_allowed_reply", "您尚未开通拍一拍自动回复功能, 可以咨询小助手开通拍一拍自动回复服务")
        
        self.root_admins = config.get("root_admins", ["Felix"])
        self.user_admins = config.get("user_admins", [])
        self.ignore_users = config.get("ignore_users", [])
        self.commands = config.get("commands", {})
        self.command_list = list(self.commands.keys())+['?'+c for c in self.commands.values()]+['？'+c for c in self.commands.values()]
        self.help_general_admin = config.get("help_general_admin", "")
        self.help_general_user = config.get("help_general_user", "")
        self.help_keyword_self = config.get("help_keyword_self", "")
        self.help_keyword_admin = config.get("help_keyword_admin", "")
        self.help_delay = config.get("help_delay", "")
        self.help_permission = config.get("help_permission", "")
        self.help_recharge =  config.get("help_recharge", "")
        self.help_query = config.get("help_query", "")
        self.help_userlist = config.get("help_userlist", "")
        self.help_query_setting = config.get("help_query_setting", "")
        self.help_setting = config.get("help_setting", "")
        self.help_manage = config.get("help_manage", "")
        self.help_help = config.get("help_help", "")
        self.help_save = config.get("help_save", "")
        self.help_deadline = config.get("help_deadline", "")
        self.help_ai_reply = config.get("help_ai_reply", "")

        self.root_admin_help_msg = self.help_general_admin+'\n'+self.help_keyword_self+'\n'+self.help_keyword_admin+'\n'+self.help_delay+'\n'+self.help_permission+'\n'+self.help_recharge+'\n'+self.help_query+'\n'+self.help_userlist+'\n'+self.help_query_setting+'\n'+self.help_setting+'\n'+self.help_manage+'\n'+self.help_save+'\n'+self.help_deadline+'\n'+self.help_help
        self.admin_help_msg = self.help_general_admin+'\n'+self.help_keyword_self+'\n'+self.help_keyword_admin+'\n'+self.help_delay+'\n'+self.help_permission+'\n'+self.help_recharge+'\n'+self.help_query+'\n'+self.help_userlist+'\n'+self.help_deadline+'\n'+self.help_ai_reply+'\n'+self.help_help
        self.user_help_msg = self.help_general_user+'\n'+self.help_keyword_self+'\n'+self.help_query+'\n'+self.help_deadline+'\n'+self.help_ai_reply+'\n'+self.help_help

        self.load_from_file()
        logger.info(f'加载用户配置成功 {self.save_path}')

    def create_account(self, id, nick_name, expire_time=new_user_trial_time):
        account = UserAccount(id, nick_name, expire_time)
        DefaultKeywordsAndReply.default_keywords = self.default_keywords
        DefaultKeywordsAndReply.default_text_reply_prefix = self.default_text_reply_prefix
        DefaultKeywordsAndReply.default_text_reply_suffix = self.default_text_reply_suffix
        account.voice_reply_prefix = self.default_voice_reply_prefix
        account.voice_reply_suffix = self.default_voice_reply_suffix
        account.image_reply_prefix = self.default_image_reply_prefix
        account.image_reply_suffix = self.default_image_reply_suffix
        account.file_reply_prefix = self.default_file_reply_prefix
        account.file_reply_suffix = self.default_file_reply_suffix
        account.sharing_reply_prefix = self.default_sharing_reply_prefix
        account.sharing_reply_suffix = self.default_sharing_reply_suffix
        account.video_reply_prefix = self.default_video_reply_prefix
        account.video_reply_suffix = self.default_video_reply_suffix
        account.patpat_reply_prefix = self.default_patpat_reply_prefix
        account.patpat_reply_suffix = self.default_patpat_reply_suffix
        account.permission = self.default_permission

        if nick_name in self.root_admins:
            account.user_type = UserTYPE.ROOT_ADMIN
            logger.info(f'新增root管理员 ID:{id} 昵称:{nick_name}')
        if nick_name in self.user_admins:
            account.user_type = UserTYPE.ADMIN
            logger.info(f'新增管理员 ID:{id} 昵称:{nick_name}')
        if nick_name in self.ignore_users:
            account.user_type = UserTYPE.IGNORE_USER
            logger.info(f'新增忽略用户 ID:{id} 昵称:{nick_name}')
        self.accounts[nick_name]=account
        logger.info(f'新增用户 ID:{id} 昵称:{nick_name} 到期时间:{account.get_expired_time()}')
        return account

    def save_to_file(self):
        with open(self.save_path, 'wb') as file:
            pickle.dump(self.accounts, file)

    def load_from_file(self):
        if not exists(self.save_path):
            self.save_to_file()
        with open(self.save_path, 'rb') as file:
            self.accounts = pickle.load(file)

    def check_expired_accounts(self):
        expired_accounts = []
        for nick_name in self.accounts:
            if self.accounts[nick_name].is_expired()[0]:
                expired_accounts.append(nick_name)
        return expired_accounts
    
    def check_expired(self, nick_name):
        if self.accounts[nick_name].is_expired():
            return True
        return False


    def query_keyword(self, nick_name):
        kw = f"{nick_name} "
        if len(self.accounts[nick_name].keywords)>0:
            kw+=f'有特别关键词:\n{list(self.accounts[nick_name].keywords.keys())}'
        kw+=f'\n全局关键词：\n{DefaultKeywordsAndReply.default_keywords}'
        logger.info(kw)
        return kw
    def add_keyword(self, nick_name, keyword, reply_prefix,reply_suffix):
        self.accounts[nick_name].add_keyword(keyword,reply_prefix,reply_suffix)
        logger.info(f"{nick_name} 关键词 {keyword} 添加成功")
        return f"{nick_name} 关键词 {keyword} 添加成功!"
    def remove_keyword(self, nick_name, keyword):
        if self.accounts[nick_name].remove_keyword(keyword):
            logger.info(f"{nick_name} 关键词 {keyword} 删除成功")
            return f"{nick_name} 关键词 {keyword} 删除成功!"
        else:
            logger.info(f"{nick_name} 关键词 {keyword} 删除失败, 未找到该关键词!")
            return f"{nick_name} 关键词 {keyword} 删除失败, 未找到该关键词!"
    def clear_keyword(self, nick_name):
        self.accounts[nick_name].keywords.clear()
        logger.info(f"关键词清除成功, {nick_name} 将使用默认关键词")
        return f"关键词清除成功, {nick_name} 将使用默认关键词!"

    def process_command_keyword(self, nick_name, args):
        if self.accounts[nick_name].user_type == UserTYPE.IGNORE_USER: 
            return f""
            
        if len(args) < 1:
            logger.info( "参数错误:\n"+self.help_keyword_self+'\n'+self.help_keyword_admin)
            return "参数错误:\n"+self.help_keyword_self+'\n'+self.help_keyword_admin
        if args[0] in ['?','？','+','-','x','X']:
            command = args[0]
        elif args[0].isdigit():
            user_nick_name = list(self.accounts.keys())[int(args[0])]
            return self.process_command_keyword(user_nick_name, args[1:])
        else:
            user_nick_name = args[0]
            return self.process_command_keyword(user_nick_name, args[1:])
        
        if command in ['?','？']:
            return self.query_keyword(nick_name)
        elif command == '+' and len(args)>=3:
            return self.add_keyword(nick_name,args[1],args[2],args[3])
        elif command == '-' and len(args)>=2:
            return self.remove_keyword(nick_name,args[1])
        elif command == 'x' or args[0] =="X" and len(args)==1:
            return self.clear_keyword(nick_name)

    def process_command_delay(self, nick_name, args):
        if self.accounts[nick_name].user_type == UserTYPE.IGNORE_USER:
            return ""
        if self.accounts[nick_name].user_type == UserTYPE.USER: 
            return f"用户 {nick_name} 无此管理员权限"

        if len(args) != 4 or not args[1].isdigit() or not args[2].isdigit() or not args[3].isdigit():
            logger.info("参数错误:\n"+self.help_delay)
            return "参数错误:\n"+self.help_delay
        if args[0].isdigit():
            user_nick_name = list(self.accounts.keys())[int(args[0])]
        else:
            user_nick_name = args[0]
        self.accounts[user_nick_name].update_expire_time(int(args[1]),int(args[2]),int(args[3]))
        logger.info(f"延期成功 {user_nick_name} 服务到期时间 {self.accounts[user_nick_name].get_expired_time()}")
        
        self.save_to_file()

        return f"延期成功 {user_nick_name} 服务到期时间 {self.accounts[user_nick_name].get_expired_time()}"

    def process_command_permission(self, nick_name, args):
        if self.accounts[nick_name].user_type == UserTYPE.IGNORE_USER: 
            return ""
        if len(args) < 2 or args[2] not in ["开","关","1","0"]:
            logger.info("参数错误:\n"+self.help_permission)
            return "参数错误:\n"+self.help_permission
        if len(args) == 2:# 设置nick_name的权限
            if args[0].isdigit():
                qx = self.allow_list[int(args[0])-1]
            else:
                qx = args[0]
            if args[1].isdigit():
                op = '开' if args[1]=='1' else '关'
            else:
                op = args[1]
        elif len(args) == 3:# 设置args[0]的权限
            if self.accounts[nick_name].user_type == UserTYPE.USER:
                return f"用户 {nick_name} 无此管理员权限"
            if args[0].isdigit():
                user_nick_name = list(self.accounts.keys())[int(args[0])]
            else:
                user_nick_name = args[0]
            return self.process_command_permission(user_nick_name, args[1:])

        self.accounts[user_nick_name].set_valid_type(qx,op)
        logger.info(f"{user_nick_name} 权限修改成功 {qx}={op}")
        
        self.save_to_file()
        
        return f"{user_nick_name} 权限修改成功 {qx}={op}"

    def process_command_recharge(self, nick_name, args):
        if self.accounts[nick_name].user_type == UserTYPE.IGNORE_USER:
            return ""
        if self.accounts[nick_name].user_type == UserTYPE.USER: 
            return f"用户 {nick_name} 无此管理员权限"

        if len(args) != 2 or not args[1].isdigit():
            logger.info("参数错误:\n"+self.help_recharge)
            return "参数错误:\n"+self.help_recharge
        if args[0].isdigit():
            user_nick_name = list(self.accounts.keys())[int(args[0])]
        else:
            user_nick_name = args[0]
        self.accounts[user_nick_name].update_expire_time(0,0,int(args[1]))
        logger.info(f"充值成功 服务到期时间 {self.accounts[user_nick_name].get_expired_time()}")
        
        self.save_to_file()
        
        return f"充值成功 服务到期时间 {self.accounts[user_nick_name].get_expired_time()}"

    def process_command_query_user(self, nick_name, query):
        if query in ["关键词",'1']:
            if len(self.accounts[nick_name].keywords)<=0:
                return f"用户 {nick_name} 未设置特殊关键词, 使用默认关键词"
            return f"用户 {nick_name} 特殊关键词为：\n{list(self.accounts[nick_name].keywords.keys())}"
        elif query in ["权限" ,'2']:
            return f"用户 {nick_name} 的功能权限为：\n{self.accounts[nick_name].get_allow_types()}"
        elif query in ["到期时间",'3']:
            return f"用户 {nick_name} 服务到期时间为:\n{self.accounts[nick_name].get_expired_time()}"
        return "参数错误:\n"+self.help_query
    
    def process_command_query(self, nick_name, args):
        if self.accounts[nick_name].user_type == UserTYPE.IGNORE_USER:
            return ""
        if self.accounts[nick_name].user_type == UserTYPE.USER: 
            return f"用户 {nick_name} 无此管理员权限"
        #查询某个用户
        if len(args) == 2:
            if args[0].isdigit():
                user_nick_name = list(self.accounts.keys())[int(args[0])]
            else:
                user_nick_name = args[0]
            return self.process_command_query_user(user_nick_name, args[1])
        elif len(args) ==1 :
            return self.process_command_query_user(nick_name, args[0])

        logger.info("参数错误:\n"+self.help_query)
        return "参数错误:\n"+self.help_query

    def process_command_querysettings(self, nick_name, args):
        if self.accounts[nick_name].user_type == UserTYPE.IGNORE_USER:
            return ""
        if self.accounts[nick_name].user_type == UserTYPE.USER or nick_name not in self.root_admins: 
            return f"用户 {nick_name} 无此管理员权限"
        
        settings = f"新用户试用时长：{self.new_user_trial_time//3600}小时\n"
        settings+= f"新用户自动回复欢迎语 :{'开' if self.auto_welcome_new_user else '关'}\n欢迎语: {self.welcome_msg}\n\n"
        settings+= "Root管理员: \n"
        for r_admin in self.root_admins:
            settings+=f'\t{r_admin}\n'
        settings+="管理员:\n"
        for u_admin in self.user_admins:
            settings+=f'\t{u_admin}\n'
        settings+="忽略用户:\n"
        for user in self.ignore_users:
            settings+=f'\t{user}\n'
        return settings
    
    def process_command_settings(self, nick_name, args):
        if self.accounts[nick_name].user_type == UserTYPE.IGNORE_USER:
            return ""
        if self.accounts[nick_name].user_type == UserTYPE.USER or nick_name not in self.root_admins: 
            return f"用户 {nick_name} 无此管理员权限"
        if len(args) != 2:
            logger.info("参数错误:\n"+self.help_setting)
            return "参数错误:\n"+self.help_setting
        if args[0] in ["试用时长","1"] and args[1].isdigit():
            self.new_user_trial_time = int(args[1])
            logger.info(f'设置试用时长={args[1]}秒 成功')
            return f'设置试用时长={args[1]}秒 成功'
        if args[0] in ["欢迎语","2"] and args[1] in ["开","关","1","0"]:
            self.auto_welcome_new_user = True if args[1] in ["开","1"] else False
            logger.info(f'设置自动回复欢迎语 {"开" if self.auto_welcome_new_user else "关"}')
            return f'设置自动回复欢迎语 {"开" if self.auto_welcome_new_user else "关"}'
        return "参数错误, 未找到设置选项:\n"+self.help_setting

    def set_user_type(self, nick_name, user_type):
        if nick_name not in self.user_admins:
            self.user_admins.append(nick_name)
        if nick_name in self.ignore_users:
            self.ignore_users.remove(nick_name)
        self.accounts[nick_name].user_type = user_type

    def process_command_manage(self, nick_name, args):
        if self.accounts[nick_name].user_type == UserTYPE.IGNORE_USER:
            return ""
        if self.accounts[nick_name].user_type == UserTYPE.USER or nick_name not in self.root_admins: 
            return f"用户 {nick_name} 无此管理员权限"
        if len(args) != 2:
            logger.info("参数错误:\n"+self.help_manage)
            return "参数错误:\n"+self.help_manage
        if args[0].isdigit():
            user_nick_name = list(self.accounts.keys())[int(args[0])]
        else:
            user_nick_name = args[0]
        if args[1] == "管理员" or args[1] == "0":
            self.set_user_type(user_nick_name, UserTYPE.ADMIN)
            logger.info(f"设置 {user_nick_name} 为管理员")
            return f"设置 {user_nick_name} 为管理员"
        elif args[1] == "普通用户" or args[1] == "1":
            self.set_user_type(user_nick_name, UserTYPE.USER)
            logger.info(f"设置 {user_nick_name} 为普通用户")
            return f"设置 {user_nick_name} 为普通用户"
        elif args[1] == "忽略用户" or args[1] == "2":
            self.set_user_type(user_nick_name, UserTYPE.IGNORE_USER)
            logger.info(f"设置 {user_nick_name} 为忽略用户")
            return f"设置 {user_nick_name} 为忽略用户"
        return self.to_string()

    def process_command_help(self, nick_name, args):
        if self.accounts[nick_name].user_type == UserTYPE.IGNORE_USER:
            return ""
        if self.accounts[nick_name].user_type == UserTYPE.USER:
            return self.user_help_msg
        if self.accounts[nick_name].user_type == UserTYPE.ROOT_ADMIN:
            return self.root_admin_help_msg
        if self.accounts[nick_name].user_type == UserTYPE.ADMIN:
            return self.admin_help_msg
        
    def process_command_save(self, nick_name, args):
        if self.accounts[nick_name].user_type == UserTYPE.IGNORE_USER:
            return ""
        if self.accounts[nick_name].user_type == UserTYPE.USER or nick_name not in self.root_admins: 
            return f"用户 {nick_name} 无此管理员权限"
        self.save_to_file()
        return "保存成功"
    
    def process_command_deadline(self, nick_name, args):
        if self.accounts[nick_name].user_type == UserTYPE.IGNORE_USER:
            return ""
        if len(args) == 1:
            if args[0].isdigit():
                user_nick_name = list(self.accounts.keys())[int(args[0])]
            else:
                user_nick_name = args[0]
            return f"{user_nick_name} 服务到期时间为:\n{self.accounts[user_nick_name].get_expired_time()}"
        return f"{nick_name} 服务到期时间为:\n{self.accounts[nick_name].get_expired_time()}"
    
    def process_command_aireply(self, nick_name, args):
        if self.accounts[nick_name].user_type == UserTYPE.IGNORE_USER:
            self.accounts[nick_name].user_type = UserTYPE.USER
            return f"用户 {nick_name} 已开启 小助手自动回复"
        elif self.accounts[nick_name].user_type == UserTYPE.USER:
            self.accounts[nick_name].user_type = UserTYPE.IGNORE_USER
            return f"用户 {nick_name} 已关闭 小助手自动回复"
        elif self.accounts[nick_name].user_type == UserTYPE.ADMIN:
            self.accounts[nick_name].user_type = UserTYPE.IGNORE_USER
            return f"管理员用户 {nick_name} 已关闭 小助手自动回复, 并已失去管理员权限, 请联系Root管理员重新获取管理员权限"
        else:
            return f"用户 {nick_name} 为Root用户, 无法关闭 小助手自动回复"
        
    def process_admin_command(self, nick_name, command, args):
        if nick_name not in self.accounts:
            logger.info(f"用户 {nick_name} 不存在")
            return f"用户 {nick_name} 不存在"
        
        if command   == "关键词"  or command in ['?'+self.commands["关键词"],'？'+self.commands["关键词"]] :
            return self.process_command_keyword(nick_name, args)
        elif command == "延期"  or command in ['?'+self.commands["延期"],'？'+self.commands["延期"]] :
            return self.process_command_delay(nick_name, args)
        elif command == "权限"  or command in ['?'+self.commands["权限"],'？'+self.commands["权限"]] :
            return self.process_command_permission(nick_name, args)
        elif command == "充值"  or command in ['?'+self.commands["充值"],'？'+self.commands["充值"]] :
            return self.process_command_recharge(nick_name, args)
        elif command == "查询"  or command in ['?'+self.commands["查询"],'？'+self.commands["查询"]] :
            return self.process_command_query(nick_name, args)
        elif command == "帮助"  or command in ['?'+self.commands["帮助"],'？'+self.commands["帮助"]] :
            return self.process_command_help(nick_name,args)
        elif command == "查询设置"  or command in ['?'+self.commands["查询设置"],'？'+self.commands["查询设置"]] :
            return self.process_command_querysettings(nick_name, args)
        elif command == "用户列表"  or command in ['?'+self.commands["用户列表"],'？'+self.commands["用户列表"]] :
            return self.to_string()
        elif command == "设置"  or command in ['?'+self.commands["设置"],'？'+self.commands["设置"]] :
            return self.process_command_settings(nick_name, args)
        elif command == "管理"  or command in ['?'+self.commands["管理"],'？'+self.commands["管理"]] :
            return self.process_command_manage(nick_name, args)
        elif command == "保存"  or command in ['?'+self.commands["保存"],'？'+self.commands["保存"]] :
            return self.process_command_save(nick_name, args)
        elif command == "到期时间"  or command in ['?'+self.commands["到期时间"],'？'+self.commands["到期时间"]] :
            return self.process_command_deadline(nick_name, args)
        elif command == "小助手" or command in ['?'+self.commands["小助手"],'？'+self.commands["小助手"]] :
            return self.process_command_aireply(nick_name, args)
        elif command.startswith('?') or command.startswith('？'):
            return "无效命令, 请回复 帮助 或者 ?hp 查看命令"
        return ""

    def __str__(self):
        s = "---Account Manager---\n"
        for nick_name in self.accounts:
            s +=f'{self.accounts[nick_name]} \n'
        return s+'\n---Account Manager----'

    def to_string(self,id=False,keyword=False,allows=False,expire=True,type=True):
        s = ""
        for index,nick_name in enumerate(self.accounts):
            s +=f'-----#{index} 昵称: {nick_name}-----\n'
            if id:
                s +=f'ID: {self.accounts[nick_name].id}\n'
            if expire:
                s +=f'到期时间: {self.accounts[nick_name].get_expired_time()}\n'
            if keyword:
                s +=f'关键词: {self.query_keyword(nick_name)}\n'
            if allows:
                s +=f'权限: {self.accounts[nick_name].get_allow_types()}\n'
            if type:
                s +=f'类型: {self.accounts[nick_name].get_user_type()}\n'
        return s

if __name__ == '__main__':
    f = UserAccountMgr()
    f.create_account(1, "John", 3600)
    f.create_account(2, "Tom", -7200)

    print(f)
    f.save_to_file()
    f.load_from_file()

    print(f.check_expired_accounts())

    print(f.check_expired("John"))

    f.accounts["John"].add_keyword("hello", "你好", "再见")
    f.accounts["John"].update_expire_time(0,1,0)
    print(f.accounts["John"].is_expired())

    print(f.accounts["John"])