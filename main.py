from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
from aiogram.dispatcher.filters import Text
import config
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from yclients import YClients

bot = Bot(token=config.token)
bot.parse_mode = "Markdown"
dp = Dispatcher(bot, storage=MemoryStorage())

class MakeAppointment(StatesGroup):
    start_bot  = State()
    get_id = State()
    get_name = State()
    get_service = State()
    get_category = State()
    get_day = State()
    get_time = State()

    get_phone_number = State()
    get_fullname = State()
    get_comment = State()

    # диалог выбора специалиста
    select_staff = State()

    select_services = State()

    select_services_category = State()

    select_day_and_time = State()

class BotDialogData:
    def __init__(self):
        self.raw_data = {}
        self.user_id = None
        self.staff_name = None
        self.temp_service_ids = []
        self.service_names = []
        self.service_prices = []
        self.category_id = None
        self.day_name = None
        self.time = None
        self.full_name = None
        self.phone_number = None
        self.comment = ''

class BasicMessages:
    main_menu_template = """
Запись на прием:

Специалист: *{staff_name}*
Дата и время: *{day_and_time}*

Услуги:
{service_names}

=============

Итого: {price} ₽
    """

def prepare_main_menu_template(staff_name = "", day_name = "", time = "", service_names = "", service_prices = []):
    if not staff_name:
        staff_name = "Не выбран"
    if not day_name:
        day_and_time = "Не выбраны"
    else:
        day_and_time = "{} в {}".format(day_name, time)
    if not service_names:
        service_names = "Не выбраны"
    else:
        service_names = "\n".join(service_names)

    if not service_prices:
        price = 0
    else:
        price = sum(service_prices)

    return BasicMessages.main_menu_template.format(staff_name=staff_name, day_and_time=day_and_time, service_names=service_names, price = str(price))

def get_main_menu_keyboard(yc: YClients):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(types.InlineKeyboardButton(text="Выбрать специалиста", callback_data="StartSelectStaff"))
    keyboard.add(types.InlineKeyboardButton(text="Выбрать дату и время", callback_data="StartSelectDateAndTime"))
    keyboard.add(types.InlineKeyboardButton(text="Выбрать услуги", callback_data="StartSelectServices"))
    if yc.staff_id and yc.service_ids and yc.time:
        keyboard.add(types.InlineKeyboardButton(text="Подтвердить запись", callback_data="StartFinalDialog"))
    if yc.staff_id or yc.service_ids or yc.time:
        keyboard.add(types.InlineKeyboardButton(text="Отменить запись", callback_data="CancelEntry"))
    return keyboard

def get_staff_keyboard(yc: YClients):
    buttons = []
    for staff in yc.get_staff():
        if staff['bookable']:
            buttons.append(types.InlineKeyboardButton(text=staff['name'],
                                                    callback_data='SelectedStaff:{}'.format(staff['id']))
                                                    )
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(*buttons)
    keyboard.add(types.InlineKeyboardButton(text="Назад ❌", callback_data="ReturnToMainMenu"))
    return keyboard

def confirm_staff_keyboard(staff_id, staff_name):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.insert(types.InlineKeyboardButton(text="Подтвердить ✅", callback_data="ConfirmStaff:{}:{}".format(staff_id, staff_name)))
    keyboard.insert(types.InlineKeyboardButton(text="Отмена ❌", callback_data="ReturnToMainMenu"))
    return keyboard

def confirm_day_and_time_keyboard(time):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.insert(types.InlineKeyboardButton(text="Подтвердить ✅", callback_data="ConfirmDayAndTime:{}"))
    keyboard.insert(types.InlineKeyboardButton(text="Отмена ❌", callback_data="TIMEReturnToMainMenu"))
    return keyboard

def get_categories_keyboard(yc: YClients, dialog_data: BotDialogData):
    small_buttons = []
    big_buttons = []
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    for category_id, data in yc.get_categories_and_services().items():
        if len(data['title']) >= 18:
            big_buttons.append(types.InlineKeyboardButton(text=data['title'], 
                                                  callback_data='SelectedCategory:{}'.format(category_id))
                                                  )
        else:
            small_buttons.append(types.InlineKeyboardButton(text=data['title'], 
                                                    callback_data='SelectedCategory:{}'.format(category_id))
                                                    )
    keyboard.add(*small_buttons)
    for button in big_buttons:
        keyboard.row()
        keyboard.add(button)
    keyboard.row()

    if dialog_data.temp_service_ids:
        keyboard.add(types.InlineKeyboardButton(text="Закончить выбор ✅", callback_data="SERVICESFinishSelection"))
        keyboard.add(types.InlineKeyboardButton(text="Сбросить выбранные услуги", callback_data="SERVICESResetSelections"))
    else:
        keyboard.add(types.InlineKeyboardButton(text="Вернуться в основное меню ⬅", callback_data="ReturnToMainMenu"))
    return keyboard

def get_services_keyboard(yc: YClients, dialog_data: BotDialogData, category_id):
    small_buttons = []
    big_buttons = []
    service_names = []
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    for service in find_category_by_id(yc, category_id)['services']:
        if int(service['id']) not in dialog_data.temp_service_ids:
            if len(service['title']) >= 10:
                big_buttons.append(types.InlineKeyboardButton(text="{} | {}р".format(service['title'], str(service['price'])),
                                                        callback_data='SelectedService:{}:{}'.format(str(category_id), str(service['id'])))
                                                        )
            else:
                small_buttons.append(types.InlineKeyboardButton(text="{} | {}р".format(service['title'], str(service['price'])),
                                                        callback_data='SelectedService:{}:{}'.format(str(category_id), str(service['id'])))
                                                        )
        else:
            if len(service['title']) >= 18:
                big_buttons.append(types.InlineKeyboardButton(text="❌ Отменить выбор {}".format(service['title']),
                                                        callback_data='UnselectedService:{}:{}'.format(str(category_id), str(service['id'])))
                                                        )
            else:
                small_buttons.append(types.InlineKeyboardButton(text="❌ Отменить выбор {}".format(service['title']),
                                                        callback_data='UnselectedService:{}:{}'.format(str(category_id), str(service['id'])))
                                                        )
    for button in list(small_buttons + big_buttons):
        button:types.InlineKeyboardButton
        service_names.append(button.text)
    keyboard.add(*small_buttons)
    for button in big_buttons:
        keyboard.row()
        keyboard.add(button)
    keyboard.row()

    keyboard.add(types.InlineKeyboardButton(text="Вернуться к категориям ⬅️", callback_data="SERVICESReturnToCategories"))
    keyboard.add(types.InlineKeyboardButton(text="Отмена ❌", callback_data="ReturnToMainMenu"))
    if dialog_data.temp_service_ids:
        keyboard.add(types.InlineKeyboardButton(text="Закончить выбор ✅", callback_data="SERVICESFinishSelection"))
    return [keyboard, service_names]

def get_day_keyboard(yc: YClients):
    buttons = []
    for datetime, day in yc.get_dates().items():
        buttons.append(types.InlineKeyboardButton(text=day,
                                                   callback_data='SelectedDay:{}'.format(datetime))
                                                   )
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(*buttons)
    keyboard.add(types.InlineKeyboardButton(text="Вернуться в основное меню ⬅", callback_data="TIMEReturnToMainMenu"))
    return keyboard

def get_time_keyboard(yc: YClients):
    buttons = []
    for time in yc.get_times():
        buttons.append(types.InlineKeyboardButton(text=time['time'],
                                                   callback_data='SelectedTime:{}'.format(time['datetime']))
                                                   )
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(*buttons)
    keyboard.add(types.InlineKeyboardButton(text="Вернуться к выбору дня ", callback_data="ReturnToSelectDay"))
    return keyboard


def confirm_record_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(types.InlineKeyboardButton(text="Да ✅", callback_data="ConfirmRecord"))
    keyboard.add(types.InlineKeyboardButton(text="Нет, отменить ❌", callback_data="CancelRecord"))
    return keyboard

def skip_comment_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(types.InlineKeyboardButton(text="Пропустить", callback_data="SkipComment"))
    return keyboard

def help_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(types.InlineKeyboardButton(text="Путь от метро Трубная", callback_data="Trubnaya_way"))
    keyboard.add(types.InlineKeyboardButton(text="Путь от метро Сухаревская", callback_data="Suharevskaya_way"))
    return keyboard

def map_keyboard(map_type):
    map_types = {
        "Trubnaya_way": "https://yandex.ru/maps/213/moscow/?azimuth=0.08149242876590879&ll=37.627489%2C55.769327&mode=routes&rtext=55.767734%2C37.621923~55.770568%2C37.629736&rtt=pd&ruri=~ymapsbm1%3A%2F%2Forg%3Foid%3D63364169971&z=17",
        "Suharevskaya_way": "https://yandex.ru/maps/213/moscow/?azimuth=0.08149242876590879&ll=37.627489%2C55.769492&mode=routes&rtext=55.772240%2C37.632051~55.770568%2C37.629736&rtt=pd&ruri=ymapsbm1%3A%2F%2Ftransit%2Fstop%3Fid%3Dstation__9858914~ymapsbm1%3A%2F%2Forg%3Foid%3D63364169971&z=16.91",
    }
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(types.InlineKeyboardButton(text="Открыть в Яндекс Картах", url=map_types[map_type]))
    keyboard.add(types.InlineKeyboardButton(text="Вернуться назад", callback_data="help_back"))
    return keyboard

def find_staff_by_id(yc: YClients):
    for staff in yc.get_staff():
        if staff['id'] == int(yc.staff_id):
            return staff
    return "None"

def find_service_by_id(yc: YClients, category_id, service_id):
    for service in yc.get_categories_and_services().get(int(category_id), None)['services']:
        if service['id'] == int(service_id):
            return service
    return "None"

def find_category_by_id(yc, category_id):
    return yc.get_categories_and_services().get(int(category_id), None)

def find_raw_service_by_id(yc: YClients, service_id):
    for service in yc.get_raw_services():
        if service['id'] == int(service_id):
            return service
    return "None"

def find_time_string_by_datetime(yc, datetime):
    for time in yc.get_times():
        if time['datetime'] == datetime:
            return time['time']
    return "None"

def convert_service_ids_to_service_names(yc: YClients, service_ids):
    services = yc.get_raw_services()
    service_names = []
    for service in services:
        if int(service['id']) in service_ids:
            service_names.append("{} | {} ₽".format(service['title'], str(service['price_max'])))
    return service_names

def convert_service_ids_to_service_prices(yc: YClients, service_ids):
    services = yc.get_raw_services()
    service_prices = []
    for service in services:
        if int(service['id']) in service_ids:
            service_prices.append(service['price_max'])
    return service_prices

@dp.message_handler(commands=['start'], state = "*")
async def process_start_commmand(message: types.Message):
    message_text = """
   Котик, привет!✨ 
    """
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["Записаться на прием", "Помощь"]
    keyboard.add(*buttons)
    await message.answer(text=message_text,reply_markup=keyboard)

@dp.message_handler(commands=['help'], state='*')
@dp.message_handler(lambda message: message.text == "Помощь", state='*')
async def process_help_command(message: types.Message):
    txt = """\nЗдесь ты можешь посмотреть, как добратсья до нашей студии 🤍
Мы переехали на новый адрес: Большой Сухаревский переулок, 22 ✨"""
    await message.answer(text=txt, reply_markup=help_keyboard())

@dp.callback_query_handler(lambda call: call.data.endswith("_way"), state='*')
async def show_way(call: CallbackQuery, state: FSMContext):
    captions = {
        "Trubnaya_way": "Как пройти от Метро Трубная до студии",
        "Suharevskaya_way": "Как пройти от Метро Сухаревская до студии",
    }    
    file_name = call.data + '.jpg'
    await call.message.delete()
    await call.message.answer_photo(open(file_name, "rb"), caption=captions[call.data], reply_markup=map_keyboard(call.data))

@dp.callback_query_handler(lambda call: call.data=="help_back", state='*')
async def help_back(call: CallbackQuery, state: FSMContext):
    await process_help_command(call.message)
    await call.message.delete()

@dp.message_handler(lambda message: message.text == "Записаться на прием", state = "*")
async def make_appointment(message: types.Message, state: FSMContext):
    yc = YClients(shop_id=234592, company_id=231147)
    dialog_data = BotDialogData()
    await state.set_state(MakeAppointment.start_bot)
    await state.set_data({"data": dialog_data, "yc": yc})
    await message.answer(prepare_main_menu_template(), reply_markup=get_main_menu_keyboard(yc))

@dp.callback_query_handler(lambda call: "CancelEntry" in call.data, state = "*")
async def cancel_entry(call: CallbackQuery, state: FSMContext):
    yc = YClients(shop_id=234592, company_id=231147)
    dialog_data = BotDialogData()
    await state.set_state(MakeAppointment.start_bot)
    await state.set_data({"data": dialog_data, "yc": yc})
    await call.message.edit_text(prepare_main_menu_template(
        dialog_data.staff_name, dialog_data.day_name, dialog_data.time, dialog_data.service_names, dialog_data.service_prices), 
        reply_markup=get_main_menu_keyboard(yc))

async def return_to_main_menu_appointment(call: CallbackQuery, state: FSMContext):
    state_data = await state.get_data()
    yc: YClients = state_data["yc"]
    dialog_data: BotDialogData = state_data["data"]
    await call.message.edit_text(prepare_main_menu_template(
        dialog_data.staff_name, dialog_data.day_name, dialog_data.time, dialog_data.service_names, dialog_data.service_prices), 
        reply_markup=get_main_menu_keyboard(yc))

async def cancel_appointment(call: CallbackQuery, state: FSMContext):
    state_data = await state.get_data()
    yc: YClients = state_data["yc"]
    dialog_data: BotDialogData = state_data["data"]
    await call.message.edit_text(prepare_main_menu_template(), 
        reply_markup=get_main_menu_keyboard(yc))

# Диалог выбора специалиста
class SelectStaffDialog:
    @dp.callback_query_handler(lambda call: "StartSelectStaff" in call.data, state = "*")
    async def start_select_staff(call: CallbackQuery, state: FSMContext):
        state_data = await state.get_data()
        yc: YClients = state_data["yc"]
        await state.set_state(MakeAppointment.select_staff)
        await call.message.edit_text(text="Выберите специалиста:", reply_markup = get_staff_keyboard(yc))

    @dp.callback_query_handler(lambda call: "SelectedStaff:" in call.data, state = MakeAppointment.select_staff)
    async def confirm_dialog_selected_staff(call: CallbackQuery, state: FSMContext):
        state_data = await state.get_data()  
        yc: YClients = state_data["yc"]
        staff_id = call.data.replace("SelectedStaff:", "")
        yc.staff_id = staff_id
        await call.message.edit_text(text="Вы действительно хотите выбрать специалиста: {}".format(find_staff_by_id(yc)['name']),
                                    reply_markup=confirm_staff_keyboard(staff_id, find_staff_by_id(yc)['name']))

    @dp.callback_query_handler(lambda call: "ConfirmStaff:" in call.data, state = MakeAppointment.select_staff)
    async def confirm_selected_staff(call: CallbackQuery, state: FSMContext):
        staff_id, staff_name = call.data.replace("ConfirmStaff:", "").split(":")
        state_data = await state.get_data()
        yc: YClients = state_data["yc"]
        dialog_data = state_data["data"]
        yc.set_staff_id(int(staff_id))
        dialog_data.staff_name = staff_name
        await state.set_data({"data": dialog_data, "yc": yc})
        await return_to_main_menu_appointment(call, state)

# Диалог выбора услуг
class SelectServicesDialog:
    @dp.callback_query_handler(lambda call: "StartSelectServices" in call.data, state = "*")
    async def start_select_services(call: CallbackQuery, state: FSMContext):
        state_data = await state.get_data()
        await state.set_state(MakeAppointment.select_services_category)
        await call.message.edit_text(text="Выберите категорию:", reply_markup = get_categories_keyboard(state_data['yc'], state_data['data']))

    @dp.callback_query_handler(lambda call: "SelectedCategory:" in call.data, state = MakeAppointment.select_services_category)
    async def set_selected_category(call: CallbackQuery, state: FSMContext):
        state_data = await state.get_data()
        yc: YClients = state_data["yc"]
        dialog_data = state_data["data"]
        category_id = call.data.replace("SelectedCategory:", "")
        dialog_data.category_id = category_id
        state_data["data"] = dialog_data
        await state.set_state(MakeAppointment.get_service)
        await state.set_data(state_data)
        keyboard, service_names = get_services_keyboard(yc, dialog_data, category_id)
        await call.message.edit_text(text="Выберите услугу: {}\n{}\n\nВсего услуг в этой категории: {}".format(find_category_by_id(yc, category_id)['title'], '\n'.join(service_names), str(len(service_names))),
                                    reply_markup = keyboard)
        
    @dp.callback_query_handler(lambda call: "SelectedService:" in call.data, state = MakeAppointment.get_service)
    async def set_selected_service(call: CallbackQuery, state: FSMContext):
        state_data = await state.get_data()
        yc: YClients = state_data["yc"]
        dialog_data: BotDialogData = state_data["data"]
        service_id = call.data.replace("SelectedService:", "").split(":")[1]
        dialog_data.temp_service_ids.append(int(service_id))
        await state.set_data(state_data)
        keyboard, service_names = get_services_keyboard(yc, dialog_data, dialog_data.category_id)
        await call.message.edit_reply_markup(keyboard)

    @dp.callback_query_handler(lambda call: "UnselectedService:" in call.data, state = MakeAppointment.get_service)
    async def set_unselected_service(call: CallbackQuery, state: FSMContext):
        state_data = await state.get_data()
        yc: YClients = state_data["yc"]
        dialog_data: BotDialogData = state_data["data"]
        service_id = call.data.replace("UnselectedService:", "").split(":")[1]
        dialog_data.temp_service_ids.remove(int(service_id))
        await state.set_data(state_data)
        keyboard, service_names = get_services_keyboard(yc, dialog_data, dialog_data.category_id)
        await call.message.edit_reply_markup(keyboard)

    @dp.callback_query_handler(lambda call: "SERVICESReturnToCategories" in call.data, state = MakeAppointment.get_service)
    async def return_to_categories(call: CallbackQuery, state: FSMContext):
        state_data = await state.get_data()
        await state.set_state(MakeAppointment.select_services_category)
        await call.message.edit_text(text="Выберите категорию:", reply_markup = get_categories_keyboard(state_data['yc'], state_data['data']))

    @dp.callback_query_handler(lambda call: "SERVICESFinishSelection" in call.data, state = "*")
    async def finish_selection(call: CallbackQuery, state: FSMContext):
        state_data = await state.get_data()
        yc: YClients = state_data["yc"]
        dialog_data: BotDialogData = state_data["data"]
        yc.reset_service_ids()
        for service_id in dialog_data.temp_service_ids:
            yc.add_service_id(int(service_id))
        dialog_data.service_names = convert_service_ids_to_service_names(yc, dialog_data.temp_service_ids)
        dialog_data.service_prices = convert_service_ids_to_service_prices(yc, dialog_data.temp_service_ids)
        state_data["yc"] = yc
        state_data["data"] = dialog_data
        await state.set_data(state_data)
        await state.set_state(MakeAppointment.start_bot)
        return await return_to_main_menu_appointment(call, state)
    
    @dp.callback_query_handler(lambda call: "SERVICESResetSelections" in call.data, state = "*")
    async def reset_selections(call: CallbackQuery, state: FSMContext):
        state_data = await state.get_data()
        yc: YClients = state_data["yc"]
        dialog_data: BotDialogData = state_data["data"]
        dialog_data.service_names.clear()
        dialog_data.service_prices.clear()
        dialog_data.temp_service_ids.clear()
        yc.reset_service_ids()
        await state.set_data(state_data)
        return await return_to_main_menu_appointment(call, state)

# Диалог выбора даты и времени
class SelectTimeDialog:
    @dp.callback_query_handler(lambda call: "StartSelectDateAndTime" in call.data, state = "*")
    async def start_select_time(call: CallbackQuery, state: FSMContext):
        state_data = await state.get_data()
        yc: YClients = state_data["yc"]
        await state.set_state(MakeAppointment.select_day_and_time)
        await call.message.edit_text(text="Выберите дату:", reply_markup=get_day_keyboard(yc))

    @dp.callback_query_handler(lambda call: "SelectedDay:" in call.data, state = MakeAppointment.select_day_and_time)
    async def set_celected_time(call: CallbackQuery, state: FSMContext):
        state_data = await state.get_data()
        yc: YClients = state_data["yc"]
        dialog_data = state_data["data"]
        datetime = call.data.replace("SelectedDay:", "")
        yc.set_datetime(datetime) 
        dialog_data.day_name = yc.get_dates()[datetime]
        state_data["yc"] = yc
        await state.set_state(MakeAppointment.get_time)
        await state.set_data(state_data)
        await call.message.edit_text(text="Выберите время:", reply_markup=get_time_keyboard(yc))

    @dp.callback_query_handler(lambda call: "SelectedTime:" in call.data, state = MakeAppointment.get_time)
    async def confirm_dialog_selected_time(call: CallbackQuery, state: FSMContext):
        state_data = await state.get_data()
        yc: YClients = state_data["yc"]
        dialog_data = state_data["data"]
        time = call.data.replace("SelectedTime:", "")
        yc.set_time(time)
        dialog_data.time = find_time_string_by_datetime(yc, time)
        state_data["yc"] = yc
        state_data["data"] = dialog_data
        await state.set_data(state_data)
        await call.message.edit_text(text="Вы действительно хотите выбрать дату и время: {} в {} ?".format(dialog_data.day_name, dialog_data.time),
                                     reply_markup=confirm_day_and_time_keyboard(yc.time)
                                    )

    @dp.callback_query_handler(lambda call: "ReturnToSelectDay" in call.data, state = MakeAppointment.get_time)
    async def return_to_select_day(call: CallbackQuery, state: FSMContext):
        state_data = await state.get_data()
        yc: YClients = state_data["yc"]
        yc.set_datetime(None) 
        state_data["yc"] = yc
        await state.set_state(MakeAppointment.select_day_and_time)
        await state.set_data(state_data)
        await call.message.edit_text(text="Выберите дату:", reply_markup=get_day_keyboard(yc))

    @dp.callback_query_handler(lambda call: "ConfirmDayAndTime:" in call.data, state = MakeAppointment.get_time)
    async def confirm_selected_time(call: CallbackQuery, state: FSMContext):
        await return_to_main_menu_appointment(call, state)

    @dp.callback_query_handler(lambda call: "TIMEReturnToMainMenu" == call.data, state = "*")
    async def reject_selected_time(call: CallbackQuery, state: FSMContext):
        state_data = await state.get_data()
        yc: YClients = state_data["yc"]
        dialog_data = state_data["data"]
        dialog_data.day_name = ""
        dialog_data.time = ""
        yc.set_datetime(None)
        yc.set_time(None)
        state_data["yc"] = yc
        state_data["data"] = dialog_data
        await state.set_data(state_data)
        await state.set_state(MakeAppointment.start_bot)
        await return_to_main_menu_appointment(call, state)

@dp.callback_query_handler(lambda call: "StartFinalDialog" == call.data, state = "*")
async def start_final_dialog(call: CallbackQuery, state: FSMContext):
    state_data = await state.get_data()
    yc: YClients = state_data["yc"]
    dialog_data = state_data["data"]
    state_data['temp'] = call.message.message_id

    await call.message.edit_text("Отправьте свой номер телефона начиная с +7")
    await state.set_state(MakeAppointment.get_phone_number)
    await state.set_data(state_data)
    

@dp.message_handler(state = MakeAppointment.get_phone_number)
async def get_phone_number(message: Message, state: FSMContext):
    if not message.text.startswith("+7") and not message.text.startswith("8") and not message.text.startswith("7") and not message.text.replace("+", "").isdigit():
        await message.answer("Неверно указан номер телефона, отправьте его по примеру: +79998887766")
        return
    
    state_data = await state.get_data()
    yc: YClients = state_data["yc"]
    dialog_data = state_data["data"]

    dialog_data.phone_number = message.text
    state_data['data'] = dialog_data

    await state.set_state(MakeAppointment.get_fullname)
    await bot.delete_message(message.from_id, state_data['temp'])
    message_id = await message.answer("Отправьте своё имя")
    state_data['temp'] = message_id.message_id
    await state.set_data(state_data)


@dp.message_handler(state = MakeAppointment.get_fullname)
async def get_fullname(message: Message, state: FSMContext):
    state_data = await state.get_data()
    yc: YClients = state_data["yc"]
    dialog_data = state_data["data"]

    dialog_data.full_name = message.text
    state_data['data'] = dialog_data
    await bot.delete_message(message.from_id, state_data['temp'])
    message_id = await message.answer("Если хотите оставить комментарий, отправьте его. Если не хотите - нажмите кнопку \"Пропустить\"", reply_markup = skip_comment_keyboard())
    state_data['temp'] = message_id.message_id
    await state.set_state(MakeAppointment.get_comment)
    await state.set_data(state_data)

@dp.message_handler(state = MakeAppointment.get_comment)
async def get_comment(message: Message, state: FSMContext):
    state_data = await state.get_data()
    yc: YClients = state_data["yc"]
    dialog_data = state_data["data"]

    dialog_data.comment = message.text


    msg = """{0}
Имя: {1}
Номер телефона: {2}
{3}

Всё верно?
    """.format(prepare_main_menu_template(
        dialog_data.staff_name, dialog_data.day_name, dialog_data.time, dialog_data.service_names, dialog_data.service_prices), dialog_data.full_name, dialog_data.phone_number, ("Комментарий: " + dialog_data.comment if dialog_data.comment else ""))
    await bot.delete_message(message.from_id, state_data['temp'])
    await state.set_data(state_data)
    await message.answer(msg, reply_markup = confirm_record_keyboard())
    

@dp.callback_query_handler(lambda call: "SkipComment" == call.data, state = '*')
async def skip_comment(call: CallbackQuery, state: FSMContext):
    state_data = await state.get_data()
    yc: YClients = state_data["yc"]
    dialog_data = state_data["data"]
    msg = """{0}
Имя: {1}
Номер телефона: {2}
{3}

Всё верно?
    """.format(prepare_main_menu_template(
        dialog_data.staff_name, dialog_data.day_name, dialog_data.time, dialog_data.service_names, dialog_data.service_prices), dialog_data.full_name, dialog_data.phone_number, ("Комментарий: " + dialog_data.comment if dialog_data.comment else ""))
    await call.message.edit_text(msg, reply_markup = confirm_record_keyboard())

@dp.callback_query_handler(lambda call: "ConfirmRecord" == call.data, state = "*")
async def confirm_record(call: CallbackQuery, state: FSMContext):
    state_data = await state.get_data()
    yc: YClients = state_data["yc"]
    dialog_data = state_data["data"]

    resp = yc.send_record(dialog_data.full_name, dialog_data.phone_number, comment = dialog_data.comment)
    await call.message.edit_text("Запись успешно создана!")
    return

@dp.callback_query_handler(lambda call: "CancelRecord" == call.data, state = "*")
async def confirm_record(call: CallbackQuery, state: FSMContext):
    await state.reset_state()
    await call.message.edit_text("Запись отменена. Чтобы начать заново, нажмите кнопку \"Записаться на приём\"")
    return

@dp.callback_query_handler(lambda call: "ReturnToMainMenu" == call.data, state = "*")
async def return_to_main_menu_from_button(call: CallbackQuery, state: FSMContext):
    await state.set_state(MakeAppointment.start_bot)
    return await return_to_main_menu_appointment(call, state)

if __name__ == '__main__':
    executor.start_polling(dp)