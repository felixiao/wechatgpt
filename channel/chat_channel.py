import imp
from math import log
import os
import re
import threading
import time
from asyncio import CancelledError
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent import futures

from bridge.context import *
from bridge.reply import *
from channel.channel import Channel
from common.dequeue import Dequeue
from common import memory
from plugins import *

from useraccount.useraccount import UserAccountMgr,UserAccount,UserTYPE
from groupchat.groupchatmgr import GroupChatManager, GroupChat, Member
try:
    from voice.audio_convert import any_to_wav
except Exception as e:
    pass

handler_pool = ThreadPoolExecutor(max_workers=8)  # 处理消息的线程池


# 抽象类, 它包含了与消息通道无关的通用处理逻辑
class ChatChannel(Channel):
    name = None  # 登录的用户名
    user_id = None  # 登录的用户id
    futures = {}  # 记录每个session_id提交到线程池的future对象, 用于重置会话时把没执行的future取消掉，正在执行的不会被取消
    sessions = {}  # 用于控制并发，每个session_id同时只能有一个context在处理
    lock = threading.Lock()  # 用于控制对sessions的访问
    account_mrg = UserAccountMgr()
    group_mgr = GroupChatManager()

    def __init__(self):
        self.account_mrg.load_from_file()
        logger.info(self.account_mrg)

        self.group_mgr.create_group_chat("电子羊🐑")
        self.group_mgr.add_member("电子羊🐑", "Felix", UserTYPE.ROOT_ADMIN)
        self.group_mgr.add_member("电子羊🐑", "FIONA", UserTYPE.ADMIN)
        _thread = threading.Thread(target=self.consume)
        _thread.setDaemon(True)
        _thread.start()

    # 根据消息构造context，消息内容相关的触发项写在这里
    def _compose_context(self, ctype: ContextType, content, **kwargs):
        context = Context(ctype, content)
        context.kwargs = kwargs
        nick_name = ""
        # context首次传入时，origin_ctype是None,
        # 引入的起因是：当输入语音时，会嵌套生成两个context，第一步语音转文本，第二步通过文本生成文字回复。
        # origin_ctype用于第二步文本回复时，判断是否需要匹配前缀，如果是私聊的语音，就不需要匹配前缀
        if "origin_ctype" not in context:
            context["origin_ctype"] = ctype
        # context首次传入时，receiver是None，根据类型设置receiver
        first_in = "receiver" not in context
        if context.get("isgroup", False):  # 群聊
            if context["msg"].other_user_nickname in self.group_mgr.groupchats:
                logger.info(f"收到群聊 {context['msg'].other_user_nickname} 的消息\n{context}")

        # 群名匹配过程，设置session_id和receiver
        if first_in:  # context首次传入时，receiver是None，根据类型设置receiver
            config = conf()
            cmsg = context["msg"]
            user_data = conf().get_user_data(cmsg.from_user_id)
            context["openai_api_key"] = user_data.get("openai_api_key")
            context["gpt_model"] = user_data.get("gpt_model")
            if context.get("isgroup", False):
                group_name = cmsg.other_user_nickname
                group_id = cmsg.other_user_id
                
                group_name_white_list = config.get("group_name_white_list", [])
                group_name_keyword_white_list = config.get("group_name_keyword_white_list", [])
                if any(
                    [
                        group_name in group_name_white_list,
                        "ALL_GROUP" in group_name_white_list,
                        check_contain(group_name, group_name_keyword_white_list),
                        group_name in self.group_mgr.groupchats,
                    ]
                ):
                    group_chat_in_one_session = conf().get("group_chat_in_one_session", [])
                    session_id = cmsg.actual_user_id
                    if any(
                        [
                            group_name in group_chat_in_one_session,
                            "ALL_GROUP" in group_chat_in_one_session,
                        ]
                    ):
                        session_id = group_id
                else:
                    return None
                context["session_id"] = session_id
                context["receiver"] = group_id
            else:
                context["session_id"] = cmsg.other_user_id
                context["receiver"] = cmsg.other_user_id
            e_context = PluginManager().emit_event(EventContext(Event.ON_RECEIVE_MESSAGE, {"channel": self, "context": context}))
            context = e_context["context"]
            if e_context.is_pass() or context is None:
                return context
            if cmsg.from_user_id == self.user_id and not config.get("trigger_by_self", True):
                logger.debug("[WX]self message skipped")
                return None
            
        

        # 消息内容匹配过程，并处理content
        if ctype == ContextType.TEXT:
            if first_in and "」\n- - - - - - -" in content:  # 初次匹配 过滤引用消息
                logger.debug(content)
                logger.debug("[WX]reference query skipped")
                return None

            nick_name_black_list = conf().get("nick_name_black_list", [])
            if context.get("isgroup", False):  # 群聊
                # 校验关键字
                match_prefix = check_prefix(content, self.group_mgr.keyword_at)
                if match_prefix is not None:
                    logger.info(f"检查群聊 {context['msg'].other_user_nickname} 包含关键词 {match_prefix}")
                
                match_prefix = check_prefix(content, conf().get("group_chat_prefix"))
                match_contain = check_contain(content, conf().get("group_chat_keyword"))
                flag = False
                if context["msg"].to_user_id != context["msg"].actual_user_id:
                    if match_prefix is not None or match_contain is not None:
                        flag = True
                        if match_prefix:
                            content = content.replace(match_prefix, "", 1).strip()
                    if context["msg"].is_at:
                        nick_name = context["msg"].actual_user_nickname
                        if nick_name and nick_name in nick_name_black_list:
                            # 黑名单过滤
                            logger.warning(f"[WX] Nickname {nick_name} in In BlackList, ignore")
                            return None

                        logger.info("[WX]receive group at")
                        if not conf().get("group_at_off", False):
                            flag = True
                        pattern = f"@{re.escape(self.name)}(\u2005|\u0020)"
                        subtract_res = re.sub(pattern, r"", content)
                        if isinstance(context["msg"].at_list, list):
                            for at in context["msg"].at_list:
                                pattern = f"@{re.escape(at)}(\u2005|\u0020)"
                                subtract_res = re.sub(pattern, r"", subtract_res)
                        if subtract_res == content and context["msg"].self_display_name:
                            # 前缀移除后没有变化，使用群昵称再次移除
                            pattern = f"@{re.escape(context['msg'].self_display_name)}(\u2005|\u0020)"
                            subtract_res = re.sub(pattern, r"", content)
                        content = subtract_res
                if not flag:
                    if context["origin_ctype"] == ContextType.VOICE:
                        logger.info("[WX]receive group voice, but checkprefix didn't match")
                    return None
            else:  # 单聊
                nick_name = context["msg"].from_user_nickname
                friend_nick_name = context["msg"].other_user_nickname
                friend_user_id = context["msg"].other_user_id
                if nick_name and nick_name in nick_name_black_list:
                    # 黑名单过滤
                    logger.warning(f"[WX] Nickname '{nick_name}' in In BlackList, ignore")
                    return None
                #################################################################################
                ## 单聊匹配指定用户关键词  ########################################################
                #################################################################################

                #### 使用动态白名单 UserAccountMgr
                # 1. 检查是否在UaserAccountMgr中
                if nick_name in self.account_mrg.accounts:
                    account = self.account_mrg.accounts[nick_name]
                    res,content = self._preprocess_msg_per_user(context, content,account)
                    if res==0:
                        return None
                elif not conf().get("single_chat_white_list", True):
                    # 4. 未开启仅白名单模式时，若不在已知用户列表中，新增用户
                    logger.info("检测到新用户，使用默认关键词与前后缀")
                    newaccount = self.account_mrg.create_account(context["msg"].from_user_id, nick_name)
                    self.account_mrg.save_to_file()
                    if self.account_mrg.auto_welcome_new_user and newaccount.user_type != UserTYPE.IGNORE_USER:
                        self._send_reply(context, Reply(ReplyType.TEXT, self.account_mrg.welcome_msg))
                    res,content = self._preprocess_msg_per_user(context, content,newaccount)
                    if res==0:
                        return None
                else:#开启单聊白名单模式，仅single_chat_prefix_and_reply_per_user 中用户才能触发
                    return None
            logger.info(f'开始检查绘画关键词')
            content = content.strip()
            img_match_prefix = check_prefix(content, conf().get("image_create_prefix"))
            if img_match_prefix:
                if self.account_mrg.accounts[nick_name].permission["画图"]:
                    content = content.replace(img_match_prefix, "", 1)
                    context.type = ContextType.IMAGE_CREATE
                    logger.info(f"匹配到绘画关键词: {img_match_prefix}，且已开通AI绘图服务，即将开始创作")
                else:
                    self._send_reply(context,Reply(ReplyType.TEXT, f'您尚未开通AI绘图权限, 可以咨询小助手开通AI绘图服务'))
                    return None
            else:
                context.type = ContextType.TEXT
            context.content = content.strip()
            logger.info(f"过滤后的内容：{content}")
            if nick_name!="" and "desire_rtype" not in context and self.account_mrg.accounts[nick_name].permission["语音回复"] and ReplyType.VOICE not in self.NOT_SUPPORT_REPLYTYPE:
                context["desire_rtype"] = ReplyType.VOICE
        elif context.type == ContextType.VOICE:
            if nick_name!="" and "desire_rtype" not in context and self.account_mrg.accounts[nick_name].permission["语音回复"] and ReplyType.VOICE not in self.NOT_SUPPORT_REPLYTYPE:
                context["desire_rtype"] = ReplyType.VOICE
        elif context.type == ContextType.ACCEPT_FRIEND:
            logger.info(f"收到好友请求: context: {context}")
            if self.account_mrg.auto_welcome_new_user:
                self._send_reply(context, Reply(ReplyType.TEXT, self.account_mrg.welcome_msg))

        logger.info(f"最后的内容：{content}")
        return context

    def _preprocess_msg_per_user(self, context: Context,content, account: UserAccount):
        """return: 0:不需要处理 
                   1:需要处理
        """
        logger.info(f"收到 {context['origin_ctype']} 消息")
        if account.user_type == UserTYPE.IGNORE_USER:
            return 0,""
        # logger.info(f"检查用户关键词 {self.account_mrg.command_list}")
        match_prefix = check_prefix(content, self.account_mrg.command_list)
        if match_prefix is not None:
            content = content.replace(match_prefix, "", 1).strip()
            logger.info(f"匹配到命令：{match_prefix}，过滤后的内容：{content}")
            context["keyword"] = match_prefix
            context["command"] = True
            args = content.split(' ')
            args = [a for a in args if a != '']
            logger.info(f'命令参数：{args}')
            msg = self.account_mrg.process_admin_command(account.nick_name, match_prefix,args)
            self._send_reply(context, Reply(ReplyType.TEXT, msg))
            return 0,""
        else:
            logger.info(f'未匹配到命令, 内容 {content}')

        # 2. 检查是否过期
        if account.is_expired()[0]:
            logger.info(f"用户{account.nick_name}服务已过期，不再处理消息")
            self._send_reply(context, Reply(ReplyType.TEXT, account.is_expired()[1]))
            return 0,""
        # 3. 匹配关键词和检查允许消息类型
        match_prefix = check_prefix(content, account.get_keywords())
        context["keyword"] = match_prefix
        if match_prefix is not None:  # 判断如果匹配到自定义前缀，则返回过滤掉前缀+空格后的内容
            content = content.replace(match_prefix, "", 1).strip()
            logger.info(f"匹配到关键词：{match_prefix}，过滤后的内容：{content}")
            return 1,content
        elif context["origin_ctype"] == ContextType.VOICE:  # 如果源消息是私聊的语音消息，允许不匹配关键词，放宽条件
            context["keyword"] = "voice"
            logger.info(f"收到语音消息")
            if account.permission["语音"]:
                logger.info(f"允许语音消息")
                return 1,content
            else:
                logger.info(f"不允许语音消息")
                self._send_reply(context, Reply(ReplyType.TEXT, self.account_mrg.voice_not_allowed_reply))
                return 0,content
        elif context["origin_ctype"] == ContextType.IMAGE:  # 如果源消息是私聊的图片消息，允许不匹配关键词
            context["keyword"] = "image"
            logger.info(f"收到图片消息")
            if account.permission["图片"]:
                logger.info(f"允许图片消息")
                return 1,content
            else:
                logger.info(f"不允许图片消息")
                self._send_reply(context, Reply(ReplyType.TEXT, self.account_mrg.image_not_allowed_reply))
                return 0,content
        elif context["origin_ctype"] == ContextType.FILE:  # 如果源消息是私聊的文件消息，允许不匹配关键词
            context["keyword"] = "file"
            logger.info(f"收到文件消息")
            if account.permission["文件"]:
                logger.info(f"允许文件消息")
                return 1,content
            else:
                logger.info(f"不允许文件消息")
                self._send_reply(context, Reply(ReplyType.TEXT, self.account_mrg.file_not_allowed_reply))
                return 0,content
        elif context["origin_ctype"] == ContextType.SHARING:  # 如果源消息是私聊的链接消息，允许不匹配关键词
            context["keyword"] = "sharing"
            logger.info(f"收到链接消息")
            if account.permission["链接"]:
                logger.info(f"允许链接消息")
                return 1,content
            else:
                logger.info(f"不允许链接消息")
                self._send_reply(context, Reply(ReplyType.TEXT, self.account_mrg.sharing_not_allowed_reply))
                return 0,content
        elif context["origin_ctype"] == ContextType.VIDEO:  # 如果源消息是私聊的视频消息，允许不匹配关键词
            context["keyword"] = "video"
            logger.info(f"收到视频消息")
            if account.permission["视频"]:
                logger.info(f"允许视频消息")
                return 1,content
            else:
                logger.info(f"不允许视频消息")
                self._send_reply(context, Reply(ReplyType.TEXT, self.account_mrg.video_not_allowed_reply))
                return 0,content
        elif context["origin_ctype"] == ContextType.PATPAT:  # 如果源消息是私聊的拍一拍消息，允许不匹配关键词
            context["keyword"] = "patpat"
            logger.info(f"收到拍一拍消息")
            if account.permission["拍一拍"]:
                logger.info(f"允许拍一拍消息")
                return 1,content
            else:
                logger.info(f"不允许拍一拍消息")
                self._send_reply(context, Reply(ReplyType.TEXT, self.account_mrg.patpat_not_allowed_reply))
                return 0,content
        logger.info(f"未匹配到关键词 或者 收到消息类型不允许处理: {content}")
        return 1,content

    def _handle(self, context: Context):
        if context is None or not context.content:
            return
        logger.debug("[WX] ready to handle context: {}".format(context))
        # reply的构建步骤
        reply = self._generate_reply(context)

        logger.debug("[WX] ready to decorate reply: {}".format(reply))
        # reply的包装步骤
        reply = self._decorate_reply(context, reply)

        # reply的发送步骤
        self._send_reply(context, reply)

    def _generate_reply(self, context: Context, reply: Reply = Reply()) -> Reply:
        e_context = PluginManager().emit_event(
            EventContext(
                Event.ON_HANDLE_CONTEXT,
                {"channel": self, "context": context, "reply": reply},
            )
        )
        reply = e_context["reply"]
        if not e_context.is_pass():
            logger.debug("[WX] ready to handle context: type={}, content={}".format(context.type, context.content))
            if context.type == ContextType.TEXT or context.type == ContextType.IMAGE_CREATE:  # 文字和图片消息
                context["channel"] = e_context["channel"]
                reply = super().build_reply_content(context.content, context)
            elif context.type == ContextType.VOICE:  # 语音消息
                cmsg = context["msg"]
                cmsg.prepare()
                file_path = context.content
                wav_path = os.path.splitext(file_path)[0] + ".wav"
                try:
                    any_to_wav(file_path, wav_path)
                except Exception as e:  # 转换失败，直接使用mp3，对于某些api，mp3也可以识别
                    logger.warning("[WX]any to wav error, use raw path. " + str(e))
                    wav_path = file_path
                # 语音识别
                reply = super().build_voice_to_text(wav_path)
                # 删除临时文件
                try:
                    os.remove(file_path)
                    if wav_path != file_path:
                        os.remove(wav_path)
                except Exception as e:
                    pass
                    # logger.warning("[WX]delete temp file error: " + str(e))

                if reply.type == ReplyType.TEXT:
                    new_context = self._compose_context(ContextType.TEXT, reply.content, **context.kwargs)
                    if new_context:
                        reply = self._generate_reply(new_context)
                    else:
                        return
            elif context.type == ContextType.IMAGE:  # 图片消息，当前仅做下载保存到本地的逻辑
                memory.USER_IMAGE_CACHE[context["session_id"]] = {
                    "path": context.content,
                    "msg": context.get("msg")
                }
            elif context.type == ContextType.SHARING:  # 分享信息，当前无默认逻辑
                pass
            elif context.type == ContextType.FUNCTION or context.type == ContextType.FILE:  # 文件消息及函数调用等，当前无默认逻辑
                pass
            else:
                logger.warning("[WX] unknown context type: {}".format(context.type))
                return
        return reply

    def _decorate_reply(self, context: Context, reply: Reply) -> Reply:
        if reply and reply.type:
            e_context = PluginManager().emit_event(
                EventContext(
                    Event.ON_DECORATE_REPLY,
                    {"channel": self, "context": context, "reply": reply},
                )
            )
            reply = e_context["reply"]
            desire_rtype = context.get("desire_rtype")
            if not e_context.is_pass() and reply and reply.type:
                if reply.type in self.NOT_SUPPORT_REPLYTYPE:
                    logger.error("[WX]reply type not support: " + str(reply.type))
                    reply.type = ReplyType.ERROR
                    reply.content = "不支持发送的消息类型: " + str(reply.type)

                if reply.type == ReplyType.TEXT:
                    reply_text = reply.content
                    logger.info("回复内容为None" if reply_text is None else "回复内容不为空")
                    if desire_rtype == ReplyType.VOICE and ReplyType.VOICE not in self.NOT_SUPPORT_REPLYTYPE:
                        reply = super().build_text_to_voice(reply.content)
                        return self._decorate_reply(context, reply)
                    if context.get("isgroup", False):
                        if not context.get("no_need_at", False):
                            reply_text = "@" + context["msg"].actual_user_nickname + "\n" + reply_text.strip()
                        reply_text = conf().get("group_chat_reply_prefix", "") + reply_text + conf().get("group_chat_reply_suffix", "")
                    else:
                        #################################################################################
                        ## 单聊回复前缀后缀  #############################################################
                        #################################################################################
                        # perusersettings = conf().get("single_chat_prefix_and_reply_per_user", {})
                        # 检测到指定用户的单独设置
                        friend_nick_name = context["msg"].other_user_nickname
                        logger.info(f"回复{friend_nick_name} {reply_text}")
                        if friend_nick_name in self.account_mrg.accounts:
                            account = self.account_mrg.accounts[friend_nick_name]
                            if account.is_expired()[0]:
                                reply_text = account.is_expired()[1]
                            elif context["origin_ctype"] == ContextType.TEXT:
                                keyword = context['keyword']
                                reply_text = account.get_reply_prefix(keyword) + reply_text + account.get_reply_suffix(keyword) 
                            elif context["origin_ctype"] == ContextType.VOICE:
                                reply_text = account.voice_reply_prefix + reply_text + account.voice_reply_suffix
                            elif context["origin_ctype"] == ContextType.IMAGE:
                                reply_text = account.image_reply_prefix + reply_text + account.image_reply_suffix
                            elif context["origin_ctype"] == ContextType.SHARING:
                                reply_text = account.sharing_reply_prefix + reply_text + account.sharing_reply_suffix
                            elif context["origin_ctype"] == ContextType.FILE:
                                reply_text = account.file_reply_prefix + reply_text + account.file_reply_suffix
                        else: 
                            reply_text = conf().get("single_chat_reply_prefix", "") + reply_text + conf().get("single_chat_reply_suffix", "")
                    reply.content = reply_text
                elif reply.type == ReplyType.ERROR or reply.type == ReplyType.INFO:
                    reply.content = "[" + str(reply.type) + "]\n" + reply.content
                elif reply.type == ReplyType.IMAGE_URL or reply.type == ReplyType.VOICE or reply.type == ReplyType.IMAGE or reply.type == ReplyType.FILE or reply.type == ReplyType.VIDEO or reply.type == ReplyType.VIDEO_URL:
                    pass
                else:
                    logger.error("[WX] unknown reply type: {}".format(reply.type))
                    return
            if desire_rtype and desire_rtype != reply.type and reply.type not in [ReplyType.ERROR, ReplyType.INFO]:
                logger.warning("[WX] desire_rtype: {}, but reply type: {}".format(context.get("desire_rtype"), reply.type))
            return reply

    def _send_reply(self, context: Context, reply: Reply):
        if reply and reply.type:
            e_context = PluginManager().emit_event(
                EventContext(
                    Event.ON_SEND_REPLY,
                    {"channel": self, "context": context, "reply": reply},
                )
            )
            reply = e_context["reply"]
            if not e_context.is_pass() and reply and reply.type:
                logger.debug("[WX] ready to send reply: {}, context: {}".format(reply, context))
                self._send(reply, context)

    def _send(self, reply: Reply, context: Context, retry_cnt=0):
        try:
            self.send(reply, context)
        except Exception as e:
            logger.error("[WX] sendMsg error: {}".format(str(e)))
            if isinstance(e, NotImplementedError):
                return
            logger.exception(e)
            if retry_cnt < 2:
                time.sleep(3 + 3 * retry_cnt)
                self._send(reply, context, retry_cnt + 1)

    def _success_callback(self, session_id, **kwargs):  # 线程正常结束时的回调函数
        logger.debug("Worker return success, session_id = {}".format(session_id))

    def _fail_callback(self, session_id, exception, **kwargs):  # 线程异常结束时的回调函数
        logger.exception("Worker return exception: {}".format(exception))

    def _thread_pool_callback(self, session_id, **kwargs):
        def func(worker: Future):
            try:
                worker_exception = worker.exception()
                if worker_exception:
                    self._fail_callback(session_id, exception=worker_exception, **kwargs)
                else:
                    self._success_callback(session_id, **kwargs)
            except CancelledError as e:
                logger.info("Worker cancelled, session_id = {}".format(session_id))
            except Exception as e:
                logger.exception("Worker raise exception: {}".format(e))
            with self.lock:
                self.sessions[session_id][1].release()

        return func

    def produce(self, context: Context):
        session_id = context["session_id"]
        with self.lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = [
                    Dequeue(),
                    threading.BoundedSemaphore(conf().get("concurrency_in_session", 4)),
                ]
            if context.type == ContextType.TEXT and context.content.startswith("#"):
                self.sessions[session_id][0].putleft(context)  # 优先处理管理命令
            else:
                self.sessions[session_id][0].put(context)

    # 消费者函数，单独线程，用于从消息队列中取出消息并处理
    def consume(self):
        while True:
            with self.lock:
                session_ids = list(self.sessions.keys())
                for session_id in session_ids:
                    context_queue, semaphore = self.sessions[session_id]
                    if semaphore.acquire(blocking=False):  # 等线程处理完毕才能删除
                        if not context_queue.empty():
                            context = context_queue.get()
                            logger.debug("[WX] consume context: {}".format(context))
                            future: Future = handler_pool.submit(self._handle, context)
                            future.add_done_callback(self._thread_pool_callback(session_id, context=context))
                            if session_id not in self.futures:
                                self.futures[session_id] = []
                            self.futures[session_id].append(future)
                        elif semaphore._initial_value == semaphore._value + 1:  # 除了当前，没有任务再申请到信号量，说明所有任务都处理完毕
                            self.futures[session_id] = [t for t in self.futures[session_id] if not t.done()]
                            assert len(self.futures[session_id]) == 0, "thread pool error"
                            del self.sessions[session_id]
                        else:
                            semaphore.release()
            time.sleep(0.1)

    # 取消session_id对应的所有任务，只能取消排队的消息和已提交线程池但未执行的任务
    def cancel_session(self, session_id):
        with self.lock:
            if session_id in self.sessions:
                for future in self.futures[session_id]:
                    future.cancel()
                cnt = self.sessions[session_id][0].qsize()
                if cnt > 0:
                    logger.info("Cancel {} messages in session {}".format(cnt, session_id))
                self.sessions[session_id][0] = Dequeue()

    def cancel_all_session(self):
        with self.lock:
            for session_id in self.sessions:
                for future in self.futures[session_id]:
                    future.cancel()
                cnt = self.sessions[session_id][0].qsize()
                if cnt > 0:
                    logger.info("Cancel {} messages in session {}".format(cnt, session_id))
                self.sessions[session_id][0] = Dequeue()


def check_prefix(content, prefix_list):
    if not prefix_list:
        return None
    for prefix in prefix_list:
        # logger.info(f"{prefix} chech with {content}")
        if content.startswith(prefix):
            # logger.info(f"{content} startswith {prefix}")
            return prefix
    return None


def check_contain(content, keyword_list):
    if not keyword_list:
        return None
    for ky in keyword_list:
        if content.find(ky) != -1:
            return True
    return None
