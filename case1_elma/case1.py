import pandas as pd
import os

# Получаем путь к папке, где лежит этот питон-файл
current_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(current_dir, 'data.csv')

print("Загрузка данных...")
# 1. Загрузка и подготовка
df = pd.read_csv(file_path, encoding='utf-8-sig')
df['Timestamp'] = pd.to_datetime(df['Timestamp'])
df = df.sort_values(by=['ProcessInstanceId', 'EventIndex']).reset_index(drop=True)

# Отфильтровываем только закрытые задачи (нужно для проверки ролей)
completed_tasks = df[df['EventType'] == 'task_completed']

final_anomalies = []

# ==========================================
# 2. Поиск: Нарушение ролей (Самосогласование)
# ==========================================
role_anomalies = completed_tasks[
    (completed_tasks['ActivityName'] == 'Согласование руководителем') & 
    (completed_tasks['Role'] == 'requester')
]
for index, row in role_anomalies.iterrows():
    final_anomalies.append({
        'ProcessInstanceId': row['ProcessInstanceId'],
        'AnomalyType': 'Нарушение ролей',
        'Explanation': "Этап 'Согласование руководителем' выполнен ролью requester (заявитель) вместо manager."
    })

# ==========================================
# 3. Поиск: Аномальная скорость (< 2 минут)
# ==========================================
created = df[df['EventType'] == 'task_created'][['TaskId', 'Timestamp', 'ActivityName', 'ProcessInstanceId', 'Amount']].rename(columns={'Timestamp': 'StartTime'})
completed = df[df['EventType'] == 'task_completed'][['TaskId', 'Timestamp', 'Role']].rename(columns={'Timestamp': 'EndTime'})
tasks_merged = pd.merge(created, completed, on='TaskId')
tasks_merged['Duration_mins'] = (tasks_merged['EndTime'] - tasks_merged['StartTime']).dt.total_seconds() / 60

fast_anomalies = tasks_merged[tasks_merged['Duration_mins'] < 2]
for index, row in fast_anomalies.iterrows():
    duration_seconds = int(row['Duration_mins'] * 60)
    final_anomalies.append({
        'ProcessInstanceId': row['ProcessInstanceId'],
        'AnomalyType': 'Аномальная скорость',
        'Explanation': f"Этап '{row['ActivityName']}' выполнен за {duration_seconds} секунд (роль: {row['Role']}). Обычно занимает больше времени."
    })

# ==========================================
# 4. Поиск: Пропущенные этапы
# ==========================================
successful_procs = df[(df['EventType'] == 'process_completed') & (df['Result'] == 'fulfilled')]['ProcessInstanceId'].unique()
missing_steps = []

for proc_id in successful_procs:
    proc_data = df[df['ProcessInstanceId'] == proc_id]
    steps_done = proc_data['ActivityName'].unique()
    req_type = proc_data['RequestType'].iloc[0]
    
    if 'Проверка заявки' not in steps_done:
        missing_steps.append({'ID': proc_id, 'Missing': 'Проверка заявки'})
    if 'Согласование руководителем' not in steps_done:
        missing_steps.append({'ID': proc_id, 'Missing': 'Согласование руководителем'})
    if 'Согласование бюджета' not in steps_done:
        missing_steps.append({'ID': proc_id, 'Missing': 'Согласование бюджета'})
    if req_type == 'contract' and 'Проверка договора' not in steps_done:
        missing_steps.append({'ID': proc_id, 'Missing': 'Проверка договора (юрист)'})

for index, row in pd.DataFrame(missing_steps).iterrows():
    final_anomalies.append({
        'ProcessInstanceId': row['ID'],
        'AnomalyType': 'Пропуск обязательного этапа',
        'Explanation': f"Заявка успешно завершена (fulfilled), но в процессе отсутствует обязательный этап '{row['Missing']}'."
    })

# ==========================================
# 5. Сохранение результата
# ==========================================
final_df = pd.DataFrame(final_anomalies)
final_df = final_df.drop_duplicates() # Убираем дубликаты

# Путь для сохранения рядом с питон-файлом
output_path = os.path.join(current_dir, 'anomalies.csv')

# Сохраняем с разделителем-запятой и правильной кодировкой
final_df.to_csv(output_path, index=False, encoding='utf-8-sig', sep=',')

print(f"ГОТОВО! Найдено {len(final_df)} аномалий.")
print(f"Файл сохранен по пути: {output_path}")