import telebot
from telebot import types
from itertools import combinations
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict

TELEGRAM_BOT_TOKEN = "tele bot token goes here" # token is obtained from @/botfather on telegram
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN) 

DONE = 'done'

data = {} # use dictionary keyed by chat id to allow multiple chats happening at the same time

# class that keeps track of how an item is shared
@dataclass
class ItemShare:
    name: str
    price: float
    participants: Dict[str, int]

    @staticmethod
    def parse(message, participants):
        split = message.split()
        name = split[0]
        price = float(split[1])
        item_participants = {}
        if len(split) == 2:
            # everybody shares this
            for participant in participants:
                item_participants[participant] = 1
        else:
            for p in split[2:]:
                if p not in participants:
                    raise Exception("Item participant not in overall participants")
                item_participants[p] = 1
        return ItemShare(name, price, item_participants)

    def format(self):
        return "Item {} costs ${}, and was shared by {}.".format(self.name, self.price, ', '.join(self.participants.keys()))

@dataclass
class BillSplit:
    # dictionary of participant name -> amount the person paid
    participants: Dict[str, float] = field(default_factory=dict)
    # dictionary of item name to a list of participants who paid for that item.
    items: Dict[str, ItemShare] = field(default_factory=dict)

def is_number(s):
    """ Returns True is string is a number. """
    try:
        float(s)
        return True
    except ValueError:
        return False

def format_dict(d):
    result = []
    for k, v in d.items():
        result.append("{} paid ${}".format(k, v))
    return '\n'.join(result)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "howdy!! here's how to sbilt :D\nInstructions:\nInput names and amount paid one by one\nonly include amount if you paid\nno spacing between one name\ntype '/split' to start splitting bills!")


@bot.message_handler(commands=['split'])
def do_split(message):
    data[message.chat.id] = BillSplit() # reinitialize old data
    msg = bot.send_message(message.chat.id, "Input name 1 and amount paid (type 'done' if no more people):")
    bot.register_next_step_handler(msg, _process_name)

@bot.message_handler(commands=['stop'])
def stop(message):
    if message.chat.id in data:
        del data[message.chat.id]
    bot.reply_to(message, "Ok, byebye! To start again, please type /split.")

def _process_name(message):
    incoming_msg = message.text.strip()
    current_data: BillSplit = data[message.chat.id]
    if incoming_msg.lower() == DONE:
        msg = bot.send_message(message.chat.id, "Thanks, these are the amounts paid by everyone:\n{}\n\nNext, please key in items in the format item_name (one word) and everybody's portions. For example, if the item is nasilemak and mark and charlie each ate one portion, key in \"nasilemak 14.50 mark charlie\". If everybody shared this, then you can just type \"nasilemak 14.50\" and it defaults to everybody.".format(format_dict(current_data.participants)))
        bot.register_next_step_handler(msg, _process_items)
        return
    processed = incoming_msg.split()
    if len(processed) == 1:
        name, amt = processed[0], 0.
    if is_number(processed[-1]):
        name, amt = ' '.join(processed[:-1]), float(processed[-1])
    else:
        name, amt = ' '.join(processed), 0.
    current_data.participants[name] = amt
    msg = bot.send_message(message.chat.id, "Got it. Input name {} and amount paid (type 'done' if no more people)".format(len(current_data.participants) + 1))
    bot.register_next_step_handler(msg, _process_name)


def _process_items(message):
    incoming_msg = message.text.strip()
    current_data: BillSplit = data[message.chat.id]
    # parse the item message
    # this assumes valid input
    # TODO check for invalid input
    item = ItemShare.parse(incoming_msg, current_data.participants)
    current_data.items[item.name] = item
    remaining = sum(current_data.participants.values()) - sum(i.price for i in current_data.items.values())
    if remaining == 0:
        transactions = calculate_transactions(current_data)
        bot.send_message(message.chat.id, '\n'.join(transactions))
        return
    else:
        msg = bot.send_message(message.chat.id, "Ok. {}\nPlease key in next item. There is ${} remaining.".format(item.format(), remaining))
        return bot.register_next_step_handler(msg, _process_items)

def calculate_transactions(bill_split: BillSplit):
    net_per_person = bill_split.participants.copy()
    for item in bill_split.items.values():
        total_shares = sum(item.participants.values())
        per_share_cost = item.price / total_shares
        for p, portions in item.participants.items():
            net_per_person[p] -= per_share_cost * portions

    return find_path(net_per_person, [])

def find_path(net_per_person, output):
    def get_first_key_with_value(value):
        for k, v in net_per_person.items():
            if v == value:
                return k
        return None

    max_value = max(net_per_person.values())
    min_value = min(net_per_person.values())

    if max_value != min_value:
        max_key = get_first_key_with_value(max_value)
        min_key = get_first_key_with_value(min_value)
        result = max_value + min_value
        if result > 0:
            output.append("{} needs to pay {}: ${}".format(min_key, max_key, abs(min_value)))
            net_per_person[max_key] = result
            net_per_person[min_key] = 0.
        else:
            output.append("{} needs to pay {}: ${}".format(min_key, max_key, abs(max_value)))
            net_per_person[max_key] = 0.
            net_per_person[min_key] = result
        return find_path(net_per_person, output)
    else:
        return output

bot.polling()
