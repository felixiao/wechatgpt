import keyword
from useraccount.useraccount import UserTYPE

class GroupChatManager:
    groupchats = {}
    keyword_at = ['@Felix']

    def __init__(self):
        pass
    
    def create_group_chat(self, name):
        group_chat = GroupChat(name)
        self.groupchats[name] = group_chat
        return group_chat
    
    def add_member(self, group_name,member_name,  user_type:UserTYPE):
        self.groupchats[group_name].add_member(member_name, user_type)
    
    def remove_member(self, member):
        self.members.remove(member)
    
    def handle_message(self, sender, message):
        if sender in self.members:
            self.bot.reply_message(sender, message)
    
    def handle_system_command(self, sender, command):
        if sender in self.members and sender.is_admin():
            if command == "change_identity":
                # Logic to change member's identity
                pass
            elif command == "set_response_type":
                # Logic to set bot's response type
                pass
            elif command == "toggle_bot":
                # Logic to turn on/off the bot
                pass

class GroupChat:
    def __init__(self, name):
        self.name = name
        self.members = []
    
    def add_member(self, member, user_type:UserTYPE):
        member = Member(member, user_type)
        self.members.append(member)
    
    def remove_member(self, member):
        self.members.remove(member)
    
    def handle_message(self, sender, message):
        if sender in self.members:
            self.bot.reply_message(sender, message)
    
    def handle_system_command(self, sender, command):
        if sender in self.members and sender.is_admin():
            if command == "change_identity":
                # Logic to change member's identity
                pass
            elif command == "set_response_type":
                # Logic to set bot's response type
                pass
            elif command == "toggle_bot":
                # Logic to turn on/off the bot
                pass


class Bot:
    def __init__(self):
        self.response_type = "Text"
    
    def reply_message(self, sender, message):
        # Logic to generate reply using external LLM
        pass


class Member:
    def __init__(self, name, user_type:UserTYPE):
        self.name = name
        self.user_type = user_type
    
    def is_admin(self):
        return self.user_type == "admin" or self.user_type == "root_admin"
