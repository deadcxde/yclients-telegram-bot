import json
f = open('test_data.json', encoding='UTF-8')

data = json.load(f)

# def get_service_info(service_name):
#     for employee in data['employee']:
#         services = employee['services']
#         if service_name in services:
#             for item, item_info in services[service_name].items():
#                 print(f"{item}: {item_info['price']}")

# # Example usage
# get_service_info('пирсинг')


def get_employee_schedule_keyboard(employee_id):
    buttons = []
    for slot in data['employee'][employee_id-1]['schedule']:
        print(slot)

def cringe(employee_id, day_of_week):
    time = []
    slots = data['employee'][employee_id-1]['schedule']
    if day_of_week in slots:
        for day_of_week, day_of_week_info in slots[day_of_week].items():
            [print(day_of_week_info[i]) for i in range(len(day_of_week_info))]
get_employee_schedule_keyboard(1)
cringe(1, "monday")