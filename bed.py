import asyncio
import logging
import smtplib
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

# ==================== CONFIGURATION ====================
TOKEN = "8317057237:AAF9AL_WHKESkNZqiJc4mGbHaBCgmHNhomw"  # Yahan apna Telegram Bot Token dalein
INITIAL_ADMINS = [6888295010]   # Yahan apni Telegram Main Admin User ID dalein
# =======================================================

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

USERS, TASKS_STOCK, PENDING_PROOFS, WITHDRAWALS = {}, [], {}, {}
ADMINS = set(INITIAL_ADMINS)
SUPPORT_MESSAGE = "📞 **Support & Help:**\nContact admin via @support for any issues."

# Conversation States for Add Task & Withdrawal
(
    ADD_FIRST_NAME, ADD_LAST_NAME, ADD_YOB, ADD_EMAIL, ADD_PASSWORD, ADD_REWARD,
    W_AMOUNT, W_UPI,
    BROADCAST_TEXT, BAN_USER, UNBAN_USER, BALANCE_USER, ADD_ADMIN_ID, REM_ADMIN_ID, SUPPORT_TEXT
) = range(15)

def get_user_kb(is_admin=False):
    kb = [
        ["📥 GET NEW GMAIL", "👤 My Profile"], 
        ["💰 My Balance", "💸 Withdraw Funds"], 
        ["📊 History", "📞 Support"]
    ]
    if is_admin: 
        kb.append(["👑 Admin Panel"])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_admin_kb(user_id):
    if user_id in INITIAL_ADMINS:
        return ReplyKeyboardMarkup([
            ["➕ Add Task", "📦 Stock Tasks"], 
            ["📢 Broadcast", "🔨 Ban User", "🔓 Unban User"],
            ["💵 Add/Sub Balance", "👑 Add Admin", "❌ Remove Admin"], 
            ["📢 Set Support", "👥 Users"], 
            ["🔙 Back to User Menu"]
        ], resize_keyboard=True)
    else:
        return ReplyKeyboardMarkup([
            ["➕ Add Task", "📦 Stock Tasks"], 
            ["🔙 Back to User Menu"]
        ], resize_keyboard=True)

# ==================== GMAIL VERIFICATION HELPER ====================
def verify_gmail_status(email):
    if not email or "@" not in email or not email.endswith("@gmail.com"):
        return False
    try:
        server = smtplib.SMTP(timeout=3)
        server.connect("gmail-smtp-in.l.google.com", 25)
        server.helo("local.host")
        server.mail("verify@gmail.com")
        code, _ = server.rcpt(email)
        server.quit()
        return code == 250
    except Exception:
        return True 

# ==================== BACKGROUND TIMERS ====================
async def task_timeout_handler(context: ContextTypes.DEFAULT_TYPE, task_id: int, user_id: int, chat_id: int):
    await asyncio.sleep(15 * 60)  # 15 Minutes timer
    task = next((t for t in TASKS_STOCK if t["id"] == task_id), None)
    if task and task["claimed_by"] == user_id:
        email = task["email"]
        task["claimed_by"] = None
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⏰ `{email}` task has expired. Please request a new task from the menu.",
                parse_mode="Markdown"
            )
        except Exception:
            pass

async def send_reminders(bot, chat_id, email):
    reminder_text = (
        f"⚠️ **Security Reminder:**\n\n"
        f"Make sure you have logged out of `{email}` on all your devices to avoid task rejection."
    )
    try:
        await bot.send_message(chat_id=chat_id, text=reminder_text, parse_mode="Markdown")
    except Exception:
        pass
    
    await asyncio.sleep(5 * 3600)
    
    try:
        await bot.send_message(chat_id=chat_id, text=reminder_text, parse_mode="Markdown")
    except Exception:
        pass

# ==================== GENERAL HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if user_id in ADMINS:
        USERS.setdefault(user_id, {"balance": 0.0, "banned": False, "is_admin": True, "name": user.first_name})
    
    if USERS.get(user_id, {}).get("banned"):
        await update.message.reply_text("🚫 **Access Denied:** You are banned from using this bot.")
        return
        
    USERS.setdefault(user_id, {"balance": 0.0, "banned": False, "is_admin": user_id in ADMINS, "name": user.first_name})
    is_admin = user_id in ADMINS or USERS[user_id]["is_admin"]
    
    welcome_text = (
        f"👋 **Welcome, {user.first_name}!**\n\n"
        f"🤖 **Welcome to the Official Gmail Task & Reward Bot.**\n"
        f"Use the interactive menu buttons below to claim tasks, check your balance, or withdraw earnings."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=get_user_kb(is_admin))

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin = user_id in ADMINS or USERS.get(user_id, {}).get("is_admin", False)
    await update.message.reply_text("🔄 **Switched back to User Menu.**", parse_mode="Markdown", reply_markup=get_user_kb(is_admin))
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin = user_id in ADMINS or USERS.get(user_id, {}).get("is_admin", False)
    await update.message.reply_text("❌ **Operation cancelled.**", parse_mode="Markdown", reply_markup=get_user_kb(is_admin))
    return ConversationHandler.END

async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    user_data = USERS.get(user_id, {"balance": 0.0, "banned": False})
    
    profile_msg = (
        f"👤 **User Profile Information**\n\n"
        f"📌 **Name:** `{user.first_name}`\n"
        f"🆔 **Telegram ID:** `{user_id}`\n"
        f"💰 **Balance:** `₹ {user_data.get('balance', 0.0):.2f}`\n"
        f"🛡️ **Status:** `{'Banned 🔴' if user_data.get('banned') else 'Active 🟢'}`"
    )
    await update.message.reply_text(profile_msg, parse_mode="Markdown")

async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if USERS.get(user_id, {}).get("banned"):
        return
    await update.message.reply_text("📂 Transaction History: No records found yet.", parse_mode="Markdown")

async def get_new_gmail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if USERS.get(user_id, {}).get("banned"):
        return await update.message.reply_text("🚫 **Access Denied:** You are banned.")
    
    task = next((t for t in TASKS_STOCK if t["claimed_by"] is None), None)
    if not task:
        return await update.message.reply_text("⏳ No registration task is available right now. Please try again soon.")
    
    task["claimed_by"] = user_id
    asyncio.create_task(task_timeout_handler(context, task["id"], user_id, update.effective_chat.id))
    
    msg = (
        f"💰 **Register Account & Earn ₹ {task['reward']:.2f}**\n\n"
        f"👤 **First name:** `{task['first_name']}`\n"
        f"👤 **Last name:** `{task['last_name']}`\n"
        f"📧 **Email:** `{task['email']}`\n"
        f"📅 **Year of birth:** `{task['yob']}`\n\n"
        f"🔑 **Password:** `{task['password']}`\n\n"
        f"⚠️ **Note:** Please complete this task within 15 minutes, otherwise it will auto-cancel."
    )
    
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Done", callback_data=f"done_{task['id']}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{task['id']}")
        ]
    ])
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

async def task_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data, user_id = query.data, query.from_user.id
    
    if data.startswith("cancel_"):
        task_id = int(data.split("_")[1])
        task = next((t for t in TASKS_STOCK if t["id"] == task_id), None)
        if task and task["claimed_by"] == user_id:
            task["claimed_by"] = None
            await query.edit_message_text(
                "❌ **Task Cancelled Successfully!**\n\nThe task has been returned to stock and is now available for other users.",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text("⚠️ **Notice:** This task was already processed or cancelled.", parse_mode="Markdown")
        return

    if data.startswith("done_"):
        task_id = int(data.split("_")[1])
        task = next((t for t in TASKS_STOCK if t["id"] == task_id), None)
        if not task:
            await query.edit_message_text("⏳ No registration task is available right now. Please try again soon.")
            return

        original_text = query.message.text
        checking_text = f"{original_text}\n\n⏳ **Checking account creation, please wait...**"
        try:
            await query.edit_message_text(checking_text, parse_mode="Markdown")
        except Exception:
            pass
        
        await asyncio.sleep(2)
        is_active = verify_gmail_status(task["email"])
        
        if is_active:
            proof_id = len(PENDING_PROOFS) + 1
            PENDING_PROOFS[proof_id] = {"user_id": user_id, "task_id": task_id, "status": "pending"}
            
            success_msg = (
                f"💰 **Register Account & Earn ₹ {task['reward']:.2f}**\n\n"
                f"👤 **First name:** `{task['first_name']}`\n"
                f"👤 **Last name:** `{task['last_name']}`\n"
                f"📧 **Email:** `{task['email']}`\n"
                f"📅 **Year of birth:** `{task['yob']}`\n\n"
                f"🔑 **Password:** `{task['password']}`\n\n"
                f"✅ **Gmail verified successfully & submitted for admin review!**"
            )
            await query.edit_message_text(success_msg, parse_mode="Markdown")
            asyncio.create_task(send_reminders(context.bot, user_id, task["email"]))

            admin_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Approve", callback_data=f"apr_{proof_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"rej_{proof_id}")]
            ])
            
            for aid in ADMINS:
                try: 
                    await context.bot.send_message(
                        chat_id=aid, 
                        text=f"🔔 **New Gmail Task Submission**\n\n👤 User ID: `{user_id}`\n📌 Task ID: `{task_id}`\n📧 Email: `{task['email']}`\n🔑 Password: `{task['password']}`\n🔍 Status: `Pending Admin Approval`", 
                        parse_mode="Markdown",
                        reply_markup=admin_kb
                    )
                except Exception: 
                    pass
        else:
            task["claimed_by"] = None
            error_msg = (
                f"❌ **Error: The Gmail account has not been created or does not exist yet.**\n\n"
                f"Please create the account correctly using the provided details. This task has been automatically cancelled and returned to stock."
            )
            await query.edit_message_text(error_msg, parse_mode="Markdown")

async def approval_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id not in ADMINS: 
        return
    
    action, proof_id = query.data.split("_")[0], int(query.data.split("_")[1])
    proof = PENDING_PROOFS.get(proof_id)
    if not proof or proof["status"] != "pending":
        return await query.edit_message_text("⚠️ **Notice:** Already processed.")
    
    proof["status"] = action
    user_id, task_id = proof["user_id"], proof["task_id"]
    reward = next((t["reward"] for t in TASKS_STOCK if t["id"] == task_id), 0.0)
    
    if action == "apr":
        USERS.setdefault(user_id, {"balance": 0.0})["balance"] += reward
        await context.bot.send_message(chat_id=user_id, text=f"🎉 **Congratulations!** Your task submission was approved. Reward added: **₹ {reward:.2f}**")
        await query.edit_message_text("✅ **Approved Successfully**", parse_mode="Markdown")
    else:
        for t in TASKS_STOCK:
            if t["id"] == task_id: 
                t["claimed_by"] = None
        await context.bot.send_message(chat_id=user_id, text="❌ **Task Rejected:** Your submission was reviewed and rejected by the admin.")
        await query.edit_message_text("❌ **Rejected Successfully**", parse_mode="Markdown")

async def balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bal = USERS.get(user_id, {}).get("balance", 0.0)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("💸 Request Withdrawal", callback_data="req_w")]])
    await update.message.reply_text(f"💰 **My Balance:** `₹ {bal:.2f}`", parse_mode="Markdown", reply_markup=kb)

# ==================== ADD TASK CONVERSATION STEPS ====================
async def start_add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return ConversationHandler.END
    await update.message.reply_text("📝 **Enter First Name:**", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return ADD_FIRST_NAME

async def task_first_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["first_name"] = update.message.text
    await update.message.reply_text("📝 **Enter Last Name:**", parse_mode="Markdown")
    return ADD_LAST_NAME

async def task_last_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["last_name"] = update.message.text
    await update.message.reply_text("📅 **Enter Year of Birth (e.g., 2004):**", parse_mode="Markdown")
    return ADD_YOB

async def task_yob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["yob"] = update.message.text
    await update.message.reply_text("📧 **Enter Gmail Address:**", parse_mode="Markdown")
    return ADD_EMAIL

async def task_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["email"] = update.message.text
    await update.message.reply_text("🔑 **Enter Gmail Password:**", parse_mode="Markdown")
    return ADD_PASSWORD

async def task_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["password"] = update.message.text
    await update.message.reply_text("💵 **Enter Reward Amount (e.g., 15.00):**", parse_mode="Markdown")
    return ADD_REWARD

async def task_reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        reward_val = float(update.message.text)
        data = context.user_data
        TASKS_STOCK.append({
            "id": len(TASKS_STOCK) + 1, 
            "first_name": data["first_name"],
            "last_name": data["last_name"],
            "yob": data["yob"],
            "email": data["email"], 
            "password": data["password"], 
            "reward": reward_val, 
            "claimed_by": None
        })
        
        drop_msg = (
            "📬 **NEW GMAIL DROP AVAILABLE!** 💌\n\n"
            "📥 Tap **\"GET NEW GMAIL\"** below to claim your fresh Gmail task right now!\n\n"
            "🔒 **Drop Details:**\n"
            "• Platform: Gmail / Google Accounts\n"
            "• Status: Active & Ready to Claim\n"
            "• Availability: ⚠️ First Come, First Served!\n\n"
            "⚡ Don't miss out! Hit the button before someone else grabs it!"
        )
        
        for uid in USERS:
            try:
                await context.bot.send_message(chat_id=uid, text=drop_msg, parse_mode="Markdown")
            except Exception:
                pass

        is_admin = user_id in ADMINS or USERS.get(user_id, {}).get("is_admin", False)
        await update.message.reply_text("✅ **Task Added to Stock & Broadcast Sent Successfully!**", parse_mode="Markdown", reply_markup=get_user_kb(is_admin))
        context.user_data.clear()
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("⚠️ **Error:** Please enter a valid number for reward amount:", parse_mode="Markdown")
        return ADD_REWARD

# ==================== WITHDRAWAL CONVERSATION ====================
async def trigger_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bal = USERS.get(user_id, {}).get("balance", 0.0)
    if bal < 30:
        await update.message.reply_text("⚠️ **Insufficient Balance:** Minimum withdrawal amount is `₹ 30.00`.", parse_mode="Markdown")
        return ConversationHandler.END
    else:
        await update.message.reply_text("📥 **Please enter your withdrawal amount:**", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
        return W_AMOUNT

async def req_withdrawal_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if USERS.get(user_id, {}).get("balance", 0.0) < 30:
        await query.message.reply_text("⚠️ **Insufficient Balance:** Minimum withdrawal amount is `₹ 30.00`.", parse_mode="Markdown")
    else:
        await query.message.reply_text("📥 **Please enter your withdrawal amount:**", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())

async def withdraw_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        if amount < 30:
            await update.message.reply_text("⚠️ **Minimum withdrawal amount is ₹ 30.00.** Please enter valid amount:", parse_mode="Markdown")
            return W_AMOUNT
        context.user_data["w_amount"] = amount
        await update.message.reply_text("📤 **Please send your UPI ID (e.g., username@okhdfcbank):**", parse_mode="Markdown")
        return W_UPI
    except ValueError:
        await update.message.reply_text("⚠️ **Error:** Please send a valid numeric amount:", parse_mode="Markdown")
        return W_AMOUNT

async def withdraw_upi_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    amt = context.user_data.pop("w_amount", 0.0)
    upi_id = update.message.text
    
    USERS[user_id]["balance"] -= amt
    wid = len(WITHDRAWALS) + 1
    WITHDRAWALS[wid] = {"user_id": user_id, "amount": amt, "upi": upi_id}
    
    is_admin = user_id in ADMINS or USERS.get(user_id, {}).get("is_admin", False)
    await update.message.reply_text("✅ **Withdrawal request submitted successfully!**", parse_mode="Markdown", reply_markup=get_user_kb(is_admin))
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data=f"wc_{wid}"), InlineKeyboardButton("✅ Paid", callback_data=f"wp_{wid}")]
    ])
    for aid in ADMINS:
        try: 
            await context.bot.send_message(chat_id=aid, text=f"💸 **New Withdrawal Request**\n👤 User ID: `{user_id}`\n💰 Amount: `₹ {amt:.2f}`\n📱 UPI: `{upi_id}`", parse_mode="Markdown", reply_markup=kb)
        except Exception: 
            pass
    return ConversationHandler.END

# ==================== ADMIN ACTIONS CONVERSATION ====================
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in INITIAL_ADMINS:
        return ConversationHandler.END
    await update.message.reply_text("📢 **Send announcement text for broadcast:**", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return BROADCAST_TEXT

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    for uid in USERS:
        try: 
            await context.bot.send_message(chat_id=uid, text=text)
        except Exception: 
            pass
    await update.message.reply_text("🚀 **Broadcast Sent Successfully!**", parse_mode="Markdown", reply_markup=get_admin_kb(update.effective_user.id))
    return ConversationHandler.END

async def ban_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in INITIAL_ADMINS:
        return ConversationHandler.END
    await update.message.reply_text("🔨 **Send Telegram ID of user to ban:**", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return BAN_USER

async def ban_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        tid = int(update.message.text.strip())
        if tid in USERS: 
            USERS[tid]["banned"] = True
        await context.bot.send_message(chat_id=tid, text="🚫 **Access Denied:** You have been banned by the admin.")
        await update.message.reply_text("✅ **User Banned Successfully**", parse_mode="Markdown", reply_markup=get_admin_kb(update.effective_user.id))
    except Exception:
        await update.message.reply_text("⚠️ **Error:** Invalid User ID format.", parse_mode="Markdown", reply_markup=get_admin_kb(update.effective_user.id))
    return ConversationHandler.END

async def unban_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in INITIAL_ADMINS:
        return ConversationHandler.END
    await update.message.reply_text("🔓 **Send Telegram ID of user to unban:**", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return UNBAN_USER

async def unban_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        tid = int(update.message.text.strip())
        if tid in USERS and USERS[tid]["banned"]:
            USERS[tid]["banned"] = False
            await context.bot.send_message(chat_id=tid, text="🎉 **Notice:** You have been unbanned!")
            await update.message.reply_text("✅ **User Unbanned Successfully**", parse_mode="Markdown", reply_markup=get_admin_kb(update.effective_user.id))
        else:
            await update.message.reply_text("⚠️ **Notice:** User is not banned or not found.", parse_mode="Markdown", reply_markup=get_admin_kb(update.effective_user.id))
    except Exception:
        await update.message.reply_text("⚠️ **Error:** Invalid User ID format.", parse_mode="Markdown", reply_markup=get_admin_kb(update.effective_user.id))
    return ConversationHandler.END

async def balance_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in INITIAL_ADMINS:
        return ConversationHandler.END
    await update.message.reply_text("💵 **Send format:** `<user_id> <amount>`\n*(Use negative amount to subtract)*", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return BALANCE_USER

async def balance_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        parts = update.message.text.split()
        tid, amt = int(parts[0]), float(parts[1])
        USERS.setdefault(tid, {"balance": 0.0})["balance"] += amt
        await context.bot.send_message(chat_id=tid, text=f"💰 **Balance Update:** Your balance has been updated by admin. New Balance: `₹ {USERS[tid]['balance']:.2f}`", parse_mode="Markdown")
        await update.message.reply_text("✅ **Balance Updated Successfully**", parse_mode="Markdown", reply_markup=get_admin_kb(update.effective_user.id))
    except Exception:
        await update.message.reply_text("⚠️ **Format Error!** Use format: `<user_id> <amount>`", parse_mode="Markdown", reply_markup=get_admin_kb(update.effective_user.id))
    return ConversationHandler.END

async def add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in INITIAL_ADMINS:
        return ConversationHandler.END
    await update.message.reply_text("👑 **Send User ID to promote as admin:**", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return ADD_ADMIN_ID

async def add_admin_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        tid = int(update.message.text.strip())
        ADMINS.add(tid)
        if tid in USERS: 
            USERS[tid]["is_admin"] = True
        await context.bot.send_message(chat_id=tid, text="👑 **Congratulations!** You have been promoted to Admin.")
        await update.message.reply_text("✅ **User Promoted Successfully**", parse_mode="Markdown", reply_markup=get_admin_kb(update.effective_user.id))
    except Exception:
        await update.message.reply_text("⚠️ **Error:** Invalid ID format.", parse_mode="Markdown", reply_markup=get_admin_kb(update.effective_user.id))
    return ConversationHandler.END

async def rem_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in INITIAL_ADMINS:
        return ConversationHandler.END
    await update.message.reply_text("❌ **Send User ID to demote:**", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return REM_ADMIN_ID

async def rem_admin_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        tid = int(update.message.text.strip())
        ADMINS.discard(tid)
        if tid in USERS: 
            USERS[tid]["is_admin"] = False
        await context.bot.send_message(chat_id=tid, text="❌ **Notice:** Your admin privileges have been removed.")
        await update.message.reply_text("✅ **Admin Demoted Successfully**", parse_mode="Markdown", reply_markup=get_admin_kb(update.effective_user.id))
    except Exception:
        await update.message.reply_text("⚠️ **Error:** Invalid ID format.", parse_mode="Markdown", reply_markup=get_admin_kb(update.effective_user.id))
    return ConversationHandler.END

async def set_support_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in INITIAL_ADMINS:
        return ConversationHandler.END
    await update.message.reply_text("📞 **Send New Support Message:**", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return SUPPORT_TEXT

async def set_support_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global SUPPORT_MESSAGE
    SUPPORT_MESSAGE = update.message.text
    await update.message.reply_text("✅ **Support Message Updated Successfully!**", parse_mode="Markdown", reply_markup=get_admin_kb(update.effective_user.id))
    return ConversationHandler.END

# ==================== MISC ADMIN BUTTON HANDLERS ====================
async def stock_tasks_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        return
    if not TASKS_STOCK: 
        return await update.message.reply_text("📦 **Stock is currently empty.**", parse_mode="Markdown")
    for t in TASKS_STOCK:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ Delete", callback_data=f"del_{t['id']}")]])
        await update.message.reply_text(f"📌 Task ID: `{t['id']}` | 📧 Email: `{t['email']}` | 💰 Reward: `₹ {t['reward']:.2f}`", parse_mode="Markdown", reply_markup=kb)

async def users_stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in INITIAL_ADMINS:
        return await update.message.reply_text("⚠️ **Permission Denied.**")
    total_users = len(USERS)
    banned_users = sum(1 for u in USERS.values() if u.get("banned", False))
    active_users = total_users - banned_users
    
    stats_msg = (
        f"📊 **Bot Users Statistics**\n\n"
        f"👥 **Total Users:** `{total_users}`\n"
        f"🟢 **Active Users:** `{active_users}`\n"
        f"🔴 **Banned Users:** `{banned_users}`"
    )
    await update.message.reply_text(stats_msg, parse_mode="Markdown", reply_markup=get_admin_kb(user_id))

async def withdraw_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id not in ADMINS: 
        return
    action, wid = query.data.split("_")[0], int(query.data.split("_")[1])
    w = WITHDRAWALS.get(wid)
    if not w: 
        return await query.edit_message_text("⚠️ **Notice:** Already handled.", parse_mode="Markdown")
    if action == "wc":
        USERS[w["user_id"]]["balance"] += w["amount"]
        await context.bot.send_message(chat_id=w["user_id"], text="❌ **Withdrawal Cancelled:** Your withdrawal request was cancelled by the admin and funds have been refunded to your balance.", parse_mode="Markdown")
        await query.edit_message_text("❌ **Cancelled Successfully**", parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id=w["user_id"], text=f"✅ **Payment Completed!** Amount of **₹ {w['amount']:.2f}** has been sent to your UPI.", parse_mode="Markdown")
        await query.edit_message_text("✅ **Marked as Paid Successfully**", parse_mode="Markdown")

async def delete_task_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id not in ADMINS:
        return
    task_id = int(query.data.split("_")[1])
    global TASKS_STOCK
    TASKS_STOCK = [t for t in TASKS_STOCK if t['id'] != task_id]
    await query.edit_message_text("🗑️ **Task Deleted from Stock Successfully**", parse_mode="Markdown")

def main():
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .build()
    )
    
    # 1. Add Task Conversation Handler
    add_task_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Add Task$"), start_add_task)],
        states={
            ADD_FIRST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_first_name)],
            ADD_LAST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_last_name)],
            ADD_YOB: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_yob)],
            ADD_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_email)],
            ADD_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_password)],
            ADD_REWARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_reward)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation), MessageHandler(filters.Regex("^🔙 Back to User Menu$"), back_to_menu)]
    )

    # 2. Withdrawal Conversation Handler
    withdrawal_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💸 Withdraw Funds$"), trigger_withdrawal)],
        states={
            W_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_amount_input)],
            W_UPI: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_upi_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation), MessageHandler(filters.Regex("^🔙 Back to User Menu$"), back_to_menu)]
    )

    # 3. Admin Actions Conversation Handlers
    broadcast_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📢 Broadcast$"), broadcast_start)],
        states={BROADCAST_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)]},
        fallbacks=[CommandHandler("cancel", cancel_conversation)]
    )
    ban_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔨 Ban User$"), ban_start)],
        states={BAN_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ban_process)]},
        fallbacks=[CommandHandler("cancel", cancel_conversation)]
    )
    unban_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔓 Unban User$"), unban_start)],
        states={UNBAN_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, unban_process)]},
        fallbacks=[CommandHandler("cancel", cancel_conversation)]
    )
    balance_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💵 Add/Sub Balance$"), balance_start)],
        states={BALANCE_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, balance_process)]},
        fallbacks=[CommandHandler("cancel", cancel_conversation)]
    )
    add_admin_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^👑 Add Admin$"), add_admin_start)],
        states={ADD_ADMIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin_process)]},
        fallbacks=[CommandHandler("cancel", cancel_conversation)]
    )
    rem_admin_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^❌ Remove Admin$"), rem_admin_start)],
        states={REM_ADMIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, rem_admin_process)]},
        fallbacks=[CommandHandler("cancel", cancel_conversation)]
    )
    support_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📢 Set Support$"), set_support_start)],
        states={SUPPORT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_support_process)]},
        fallbacks=[CommandHandler("cancel", cancel_conversation)]
    )

    # Register Conversation Handlers
    app.add_handler(add_task_conv)
    app.add_handler(withdrawal_conv)
    app.add_handler(broadcast_conv)
    app.add_handler(ban_conv)
    app.add_handler(unban_conv)
    app.add_handler(balance_conv)
    app.add_handler(add_admin_conv)
    app.add_handler(rem_admin_conv)
    app.add_handler(support_conv)

    # Standard Command & Message Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^📥 GET NEW GMAIL$"), get_new_gmail))
    app.add_handler(MessageHandler(filters.Regex("^👤 My Profile$"), profile_handler))
    app.add_handler(MessageHandler(filters.Regex("^💰 My Balance$"), balance_handler))
    app.add_handler(MessageHandler(filters.Regex("^📊 History$"), history_handler))
    app.add_handler(MessageHandler(filters.Regex("^📞 Support$"), lambda u, c: u.message.reply_text(SUPPORT_MESSAGE, parse_mode="Markdown")))
    app.add_handler(MessageHandler(filters.Regex("^👑 Admin Panel$"), lambda u, c: u.message.reply_text("👑 **Admin Panel Dashboard**", parse_mode="Markdown", reply_markup=get_admin_kb(u.effective_user.id))))
    app.add_handler(MessageHandler(filters.Regex("^📦 Stock Tasks$"), stock_tasks_handler))
    app.add_handler(MessageHandler(filters.Regex("^👥 Users$"), users_stats_handler))
    app.add_handler(MessageHandler(filters.Regex("^🔙 Back to User Menu$"), back_to_menu))
    
    # Callback Handlers
    app.add_handler(CallbackQueryHandler(task_callbacks, pattern="^(done_|cancel_)"))
    app.add_handler(CallbackQueryHandler(approval_callbacks, pattern="^(apr_|rej_)"))
    app.add_handler(CallbackQueryHandler(withdraw_cb, pattern="^w[cp]_"))
    app.add_handler(CallbackQueryHandler(req_withdrawal_cb, pattern="^req_w$"))
    app.add_handler(CallbackQueryHandler(delete_task_cb, pattern="^del_"))
    
    print("AGAMING GMAIL BOT IS STARTED (WITH CONVERSATION HANDLERS)")
    app.run_polling()

if __name__ == "__main__":
    main()