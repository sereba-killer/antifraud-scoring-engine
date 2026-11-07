import pandas as pd
import numpy as np

def zagruzka_i_filtraciya(put_k_failu):
    data = pd.read_csv(put_k_failu) # Читаем датасет, пандас его преобразует в удобную двумерную табличку
    celev_oper = ['TRANSFER', 'CASH_OUT'] # Берём только те где в теории мог бы быть фрод, а именно перевод и обнал 
    filtred = data['type'].isin(celev_oper) # ставим 1 на нужные нам типы, 0 на ненужые
    tablforcheckup = data[filtred].copy() # .copy() чтобы не было варнинга, фильтруем таблицу по маске
    return tablforcheckup

def raschet_priznakov(table):
    table1 = table.sort_values(by=['nameDest','step']).copy() # Удобная сортировка как в ыйд типа группируем и сортируем как partition by ... order by
    table1['sliv_v_zero'] = (table1['oldbalanceOrg'] > 0) & (table1['amount'] == table1['oldbalanceOrg']) # Создаём новый столбец, который показывает что уход денег был на все деньги
    #table1['rassinhron'] = (table1['oldbalanceOrg'] - table1['amount']) - table1['newbalanceOrig'] # Создаём ещё столбец, если вдруг не сошлось ничё в переводе и не 0
    # Считаем рассинхрон только если на балансе было достаточно денег
    dostatochno_deneg = table1['oldbalanceOrg'] >= table1['amount'] # Смотрим чтобы на сумму ухода хватало денег, а то это может быть короче в кредит перевод и ложное срабатывание
    table1['rassinhron'] = np.where(dostatochno_deneg,(table1['oldbalanceOrg'] - table1['amount']) - table1['newbalanceOrig'],0,)#  Если денег достаточно, то смотрим рассинхрон между ушедшими деньгами и балансом
    prev_shag = table1.groupby('nameDest')['step'].shift(1) # Аналог lag в sql, нужено чтобы можно было посчитать время от прошлой до нынешней транзакции
    table1['cooldown_ot_prev'] = table1['step'] - prev_shag # Создаём столбец непосредственно сколько по времени счёт был АФК 
    #table1['my_redflag'] = ((table1['cooldown_ot_prev'].isna()) | (table1['cooldown_ot_prev'] > 500)) & (table1['oldbalanceDest'] <= 2500) & (table1['amount'] > 70000)
    drop_transfer = ((table1['type'] == 'TRANSFER')& ((table1['cooldown_ot_prev'].isna())| (table1['cooldown_ot_prev'] > 500))& (table1['oldbalanceDest'] <= 2500)) # Если застой был 500 шагов(вроде как это часы) и резко началась движуха - перевод от 70к, то это скорее всего фрод тип продал мб ненужную карту. 70к потому что если берем авг африканскую валюту, то доллар это где-то 100 с чем-то валюты, поэтому получается что это 700+ баксов и это вохможно фрод
    obnal_cashout = (table1['type'] == 'CASH_OUT') & (table1['sliv_v_zero']) # слили всё в ноль и тип вывода это обнал
    table1['podozritelniy_vyvod'] = drop_transfer | obnal_cashout # объединяем короче ччто либо первый трасфер дроп либо обнал
    return table1 

def risk_reward(table):
  temp = np.zeros(len(table))
  temp += np.where(table['sliv_v_zero'], 40, 0)  # 1е правило полный слив 40 очков
  temp += np.where(table['podozritelniy_vyvod'], 35, 0)  # 2е правило спящий дроп или обнал
  temp += np.where(table['rassinhron'].abs() > 0.01, 30, 0) # 3е правило рассинхрон баланса
  temp += np.where(table['amount'] > 200000, 15, 0) # 4е правило сумма больше 200к 
  table['risks'] = temp # сохраняем риск скор
  table['nuzhen_banan'] = (table['risks'] >= 70).astype(int) # По моей методе при риске больше 70 будет бан(ан)
  return table

def test_da_net(table):
    tp = len(table[(table['nuzhen_banan'] == 1) & (table['isFraud'] == 1)]) # Тру позитив
    fp = len(table[(table['nuzhen_banan'] == 1) & (table['isFraud'] == 0)]) # Фолз позитив
    fn = len(table[(table['nuzhen_banan'] == 0) & (table['isFraud'] == 1)]) # фолз негатив
    recall = tp/(tp+fn) # Насколько мы вообще закрыли баны
    precision = tp/(tp+fp) # Насколько мало мы забанили честных
    return tp,fp,fn,recall,precision



path = r'D:\ANTIFROD\project_anti_frod\data\paysim dataset.csv'


def start(path):
    print('Считывание базы')
    table = zagruzka_i_filtraciya(path)
    print('Считаем риск')
    table = raschet_priznakov(table)
    print('Скоринг')
    table = risk_reward(table)
    print('Считаем')
    tp, fp, fn, recall, precision = test_da_net(table)
    print('-' * 67)
    print(f'Истинно поймано (TP):   {tp}')
    print(f'Ложных банов (FP):      {fp}')
    print(f'Пропущено атак (FN):    {fn}')
    print(f'Recall (Полнота):       {recall:.2%}')
    print(f'Precision (Точность):   {precision:.2%}')
    print('-' * 67)

start(path)






"""
# Короче этот блок был для того, чтобы я мог посомтреть где ошибся в правилах и их поменять на более корректные, его можете разкомментировать и пощупать


table = zagruzka_i_filtraciya(path)
table = raschet_priznakov(table)
table = risk_reward(table)
propuski = table[(table['nuzhen_banan'] == 0) & (table['isFraud'] == 1)].copy()
print('\n' + '=' * 67)
print('АНАЛИЗ ПРОПУЩЕННОГО ФРОДА (FN):')
print('По типам операций:')
print(propuski['type'].value_counts())
print(f"\nСколько атак с суммой <= 70 000:       {(propuski['amount'] <= 70000).sum()}")
print(f"Сколько атак с oldbalanceOrg == 0:     {(propuski['oldbalanceOrg'] == 0).sum()}")
print(f"Сколько атак с oldbalanceDest > 2500:  {(propuski['oldbalanceDest'] > 2500).sum()}")
print('=' * 67)

"""