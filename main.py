# -*- coding: utf-8 -*-

**Классификация ремонтных операций**

Цель проекта - автоматизировать процедуру классификации ремонтных операций,
которая, в данный момент, осуществляется вручную.
В качестве базы данных используется общая база всех ремонтных операций по одному из видов потребительской электроники. Все ремонты, осуществляемые
на территории СНГ, заносятся в единую базу данных. Задача сотстоит в том, чтобы
отнести каждый ремонт к одному из заранее заданных типов (13 типов), которые используются в дальнейшем для для управленческого и финансового анализа сервисных операций. 
Классификация осуществляется на основании описания неисправности и ремонтных действий (текстовые данные), а также кодов неисправности, симптома, использованной запчасти, выданного акта (цифро-буквенные коды), которые все будут преобразованы в категориальные данные для передачи в нейронную сеть.

Для решения этой задачи нейронная сеть будет разбита на две подсети:
1. Первая нейронка будет работать с текстовыми данными.
   - Symptom - текстовые данные, будут преобразованы в векторную форму на
   базе BoW с применением лемматизации. Альтернативно протестируем преобразование в Embedding.
   - Fault - преобразование аналогично Symptom.
   Поля Symptom и Fault будут объеденены и обрабатываются вместе.
2. Вторая нейронка будет работать с категориальными данными.
   - Code_condition - код состояния изделия
   - Code_symptom - код симптома неисправности
   - Code_section - код неисправного блока
   - Code_repair - код ремонтной операции
   - Code_fault - код неисправности
   - Partcode - код использованной запчасти для ремонта
   - Act - код выданного акта ремонта
   
   Все коды будут переведены в последовательную цифровую форму с помощью  преобразованbz в OneHotEncoding.

Обе нейронные сети обьединяются в одну с выходным Dense слоем на 13 нейронов и
активационной функцией softmax.

Задача - достигнуть значение метрики accuracy 95%.

В связи с небольшим размером база разбита на 2 части:
90% - обучающая выборка
10% - валидационная выборка
"""

!pip install pymorphy2

# Commented out IPython magic to ensure Python compatibility.
from google.colab import drive
from google.colab import files
import numpy as np
import pandas as pd
import re

from tensorflow import keras
from tensorflow.keras import utils
from tensorflow.keras.models import Sequential, Model, load_model
from tensorflow.keras.layers import Dense, Dropout, BatchNormalization, Embedding 
from tensorflow.keras.layers import Input, concatenate, LSTM, SpatialDropout1D
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.optimizers import Adam, RMSprop
from tensorflow.keras.utils import plot_model
from tensorflow.keras.callbacks import ReduceLROnPlateau, ModelCheckpoint, EarlyStopping

from sklearn import preprocessing
from sklearn.metrics import mean_squared_error as mse
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
from sklearn.metrics import precision_score, recall_score, f1_score, roc_curve, auc

import pymorphy2
from nltk.corpus import stopwords
import nltk
nltk.download('stopwords')

import matplotlib.pyplot as plt #
# %matplotlib inline

drive.mount('/content/drive')

"""**Загрузка данных**"""

df = pd.read_excel("/content/drive/MyDrive/Colab_Notebooks/Diploma/Repairs.xlsx")
df.head(6)

"""**Подготовка данных**"""

# Убираем строки с пустыми значениями 
df.dropna(subset=["Symptom", "Fault", "Category"], axis = 0 , inplace= True)
df = df.reset_index(drop=True)

# Унифицируем данные в колонке Partcode
df['Partcode'].replace('k', 'K', regex=True, inplace=True)
df['Partcode'].replace('q', 'Q', regex=True, inplace=True)
df['Partcode'].fillna('Empty', inplace=True)

for i in range(len(df['Partcode'])):
  if df['Partcode'][i][0:1] != 'K' and df['Partcode'][i] != 'Empty':
    df['Partcode'][i] = 'K' + df['Partcode'][i]
df['Partcode'].replace('537', '536', regex=True, inplace=True)
df['Partcode'].replace('538', '536', regex=True, inplace=True)
df['Partcode'].replace('316', '536', regex=True, inplace=True)
df['Partcode'].replace('504Q', '505Q', regex=True, inplace=True)
df['Partcode'].replace('504C', '540C', regex=True, inplace=True)
df['Partcode'].replace('506', '111', regex=True, inplace=True)
df['Partcode'].replace('523', '111', regex=True, inplace=True)
df['Partcode'].replace('403', '111', regex=True, inplace=True)
df['Partcode'].replace('320', '111', regex=True, inplace=True)
df['Partcode'].replace('209', '111', regex=True, inplace=True)
df['Partcode'].replace('203', '111', regex=True, inplace=True)
df['Partcode'].replace('202', '111', regex=True, inplace=True)
df['Partcode'].replace('103', '111', regex=True, inplace=True)
df['Partcode'].replace('102', '111', regex=True, inplace=True)
df['Partcode'].replace('101', '111', regex=True, inplace=True)
df['Partcode'].replace('205', '111', regex=True, inplace=True)
df['Partcode'].replace('123Q', '511Q', regex=True, inplace=True)
df['Partcode'].replace('107Q', '511Q', regex=True, inplace=True)
df['Partcode'].replace('304W', '540W', regex=True, inplace=True)

df['Partcode'] = df['Partcode'].str[:4]

# Унифицируем данные в колонке колонку Act
df['Act'] = df['Act'].str[:3]

# Унифицируем данные в колонке Code_condition
df['Code_condition'].replace('c', 'C', regex=True, inplace=True)

df.fillna('Emp', inplace=True)

np.sort(df['Partcode'].unique())

df["Code_condition"] = df["Code_condition"].astype('category').cat.codes
df["Code_symptom"] = df["Code_symptom"].astype('category').cat.codes
df["Code_section"] = df["Code_section"].astype('category').cat.codes
df["Code_repair"] = df["Code_repair"].astype('category').cat.codes
df["Code_fault"] = df["Code_fault"].astype('category').cat.codes
df["Partcode"] = df["Partcode"].astype('category').cat.codes
df["Repair_status"] = df["Repair_status"].astype('category').cat.codes
df["Act"] = df["Act"].astype('category').cat.codes

df.head()

# Сохраняем предобработанные данные
df.to_excel('/content/drive/MyDrive/Colab_Notebooks/Diploma/RepairData_processed.xlsx', sheet_name='RepairData', index=False)

"""**Обработка данных. Подготовка классификации (yTrain)**

---


"""

# Распределение неисправностей по категориям
for cl in df['Category'].unique():
  print('Количество записей класса ', cl, ': ', df[df.Category == cl].shape[0])

# Извлекаем список имен классов для последующей классификации
className = df['Category'].unique()
print(className)

# Извлекаем соответствующие им значения категорий
classes = list(df['Category'].values)
print(classes)

# Количество уникальных категорий
nClasses = df['Category'].nunique()
print("Колличество класов:", nClasses)

#Преобразовываем категории в лэйблы
encoder = LabelEncoder()
encoder.fit(classes)
classesEncoded = encoder.transform(classes)
print(encoder.classes_)
print(classesEncoded.shape)
print(classesEncoded[:20])

# Преобразуем каждый лейбл категории в вектор
yAll = utils.to_categorical(classesEncoded, nClasses)
print(yAll.shape)
print(yAll[2])

"""**Обработка данных. Преобразуем категориальные данные в векторные для обучения нейросети**

---
"""

xAllN = np.hstack((utils.to_categorical(df['Code_condition']),
                  utils.to_categorical(df['Code_symptom']),
                  utils.to_categorical(df['Code_section']),
                  utils.to_categorical(df['Code_repair']),
                  utils.to_categorical(df['Code_fault']),
                  utils.to_categorical(df['Partcode']),
                  utils.to_categorical(df['Repair_status']),
                  utils.to_categorical(df['Act'])))

xAllN = np.array(xAllN)
print(xAllN, '\n')
xAllN.shape

"""**Обработка данных. Преобразуем текстовые данные в векторные для обучения нейросети**


"""

# Извлекаем описание симптома и неисправности, обьединяем в один список
def getXTexts(values):
  texts = []
  
  for val in values:
    currText = ""
    if (type(val[0]) == str):
      currText += val[0]
    if (type(val[1]) == str):
      currText += " " + val[1]
    
      texts.append(currText)
  
  texts = np.array(texts)
  
  return texts

# Извлекаем описание симптома и неисправности, обьединяем в один список
texts = getXTexts(df.values)
print(texts.shape)
print(texts[0])

# Удаляем пунктуационные знаки препинания и дополнительные ненужные знаки
def cleanText(dict_text):

  # Определяем, какие знаки будут удалены
  dict_text = re.sub("[\"]", "", dict_text)
  dict_text = re.sub("[()]", " ", dict_text)
  dict_text = re.sub("Выезд!", "", dict_text)
  dict_text = re.sub("[0-9]|[-—.,:;_%©«»?*!@#№$^•·&()]|[+=]|[[]|[]]|[/]|", '', dict_text)
  dict_text = re.sub(r"\r\n\t|\n|\\s|\r\t|\\n", ' ', dict_text)
  dict_text = re.sub("n", ' ', dict_text)

  # Конвертируем текст к нижнему регистру
  dict_text = dict_text.lower()
  return dict_text

# Конвертируем исходный текст в список слов с начальной формой 
def text2Words(dict_text):
  # Инициализируем инструмент для работы с морфемами
  morph = pymorphy2.MorphAnalyzer()
  # Разделяем текст посредством пробелов
  words = dict_text.split(' ')
  # Превращаем каждое слово в элемент списка
  docs = [morph.parse(word)[0].normal_form for word in words]
  #docs = [morph.parse(word)[0].normal_form for word in dict_text]
  dict_text = ' '.join(docs)
  return dict_text

# Убираем их текста стоп-слова
def textNoStop(dict_text):
  words = dict_text.split(' ')
  dict_text = [i for i in words if not i in stopword_ru]
  dict_text = ' '.join(words)
  return dict_text

# Создаем список слов, которые не будут учитываться токенайзером
stopword_ru = stopwords.words('russian')
stopword_ru.pop(26)
with open('/content/drive/MyDrive/Colab_Notebooks/Diploma/stopwords.txt') as f:
    additional_stopwords = [w.strip() for w in f.readlines() if w]
stopword_ru += additional_stopwords

dict_text = []
for i in range(len(texts)):
  dict_temp = cleanText(texts[i])
  dict_temp = text2Words(dict_temp)
  dict_temp = textNoStop(dict_temp)
  dict_text.append(dict_temp)

print(len(dict_text))
print(dict_text[:2])

# Сохраняем предобработанные данные
with open('/content/drive/MyDrive/Colab_Notebooks/Diploma/listfile.txt', 'w') as filehandle:  
    filehandle.writelines("%s\n" % place for place in dict_text)

# Загружаем предобработанные данные
dict_text = []
with open('/content/drive/MyDrive/Colab_Notebooks/Diploma/listfile.txt', 'r') as filehandle:  
    dict_text = [current_place.rstrip() for current_place in filehandle.readlines()]

# Задаем максимальное количество слов/индексов для обучения текстов
maxWordsCount = 12000

#Преобразовываем текстовые данные в числовые/векторные
tokenizer = Tokenizer(num_words=maxWordsCount, filters='', char_level=False)

# Создаем словарь частотности
tokenizer.fit_on_texts(dict_text)

# Cловарь для просмотра
print(tokenizer.word_index.items())
print("Размер словаря", len(tokenizer.word_index.items()))

# Преобразовываем текст в последовательность индексов согласно частотному словарю
textsIndexes = tokenizer.texts_to_sequences(dict_text)
print(textsIndexes)

print("Обработанный оригинальный текст:          ", dict_text [0])
print("Текст в виде последовательности индексов: ", textsIndexes[0])

"""**Создание обучающей выборки**"""

# Распределение записей в базе по количеству слов
xAllE = textsIndexes
len_xAllE = [len(x) for x in xAllE]
plt.hist(len_xAllE, 80)
plt.show()

# Выбираем оптимальную длину вектора и преобразуем входные векторы
maxlen = 50 # Ограничиваем максимальную длину текста, остальное заполняем нулями
for i in len_xAllE:
  if i > maxlen:
    xAllE[i] = xAllE[i][:maxlen]

xAllE = pad_sequences(xAllE, maxlen=maxlen)
print(xAllE)

# Данный функционал пока не используется в виду требуемых больших вычислительных реурсов
'''
# Преобразуем последовательность индексов слов в матрицу по принципу BoW
xAllE = tokenizer.sequences_to_matrix(xAllE.tolist())
# Фрагмент набора слов в виде BoW
print(xAllE[0][0:100])
'''

print(xAllE.shape)
print(xAllN.shape)
print(yAll.shape)

"""**Коллбэки**"""

# Коллбэки
reduce_lr = ReduceLROnPlateau(monitor='val_loss', factor=0.1,
                              patience=5, min_lr=0.00001)
filepath = '/content/drive/MyDrive/Colab_Notebooks/Diploma/my_best_model.hdf5'
checkpoint = ModelCheckpoint(filepath=filepath, 
                             monitor='val_loss',
                             verbose=0,
                             save_weights_only=True, 
                             save_best_only=True,
                             mode='min')

"""**Нейронная сеть на Dense и LSTM слое с применением Embedding**"""

# Делаем составную нейронную сеть для категориальных и текстовых данных
input1 = Input((xAllN.shape[1],)) # Входной слой для первой нейронки
input2 = Input((xAllE.shape[1],)) # Входной слой для второй нейронки
x1 = Dense(512, activation='relu')(input1) # Создаем ветку х11
x2 = Embedding(maxWordsCount, 70, input_length=maxlen)(input2) # Создаем ветку х2
x2 = SpatialDropout1D(0.2)(x2)
x2 = BatchNormalization()(x2)
x2 = LSTM(200)(x2)
x = concatenate([x1, x2]) # Объединяем ветки X1 и X2
x = Dense(64, activation='relu')(x)
x = Dropout(0.1)(x)
x = BatchNormalization()(x)
x = Dense(32, activation='relu')(x)
x = Dropout(0.1)(x)
x = BatchNormalization()(x)
x = Dense(nClasses, activation='softmax')(x) # Финальная классификация
model = Model((input1, input2), x) # В Model загружаем стартовые и последнюю точки

model.compile(optimizer=Adam(learning_rate=1e-3), 
              loss='categorical_crossentropy', 
              metrics=['accuracy'])

model.summary()

plot_model(model, dpi=60, show_shapes=True)

#Обучаем сеть на выборке
history = model.fit((xAllN, xAllE), 
                    yAll, 
                    epochs=20,
                    batch_size=32,
                    validation_split=0.2,
                    shuffle=True,
                    callbacks=[reduce_lr, checkpoint])

# Выводим графики ошибки
plt.plot(history.history['accuracy'], 
         label='Доля верных ответов на обучающем наборе')
plt.plot(history.history['val_accuracy'], 
         label='Доля верных ответов на проверочном наборе')
plt.xlabel('Эпоха обучения')
plt.ylabel('Доля верных ответов')
plt.legend()
plt.show()

plt.plot(history.history['loss'], 
         label='Ошибка на обучающем наборе')
plt.plot(history.history['val_loss'], 
         label='Ошибка на проверочном наборе')
plt.xlabel('Эпоха обучения')
plt.ylabel('Ошибка')
plt.legend()
plt.show()

"""**Оценка результатов**"""

# Делаем предсказание категории ремонта
pred = model.predict([xAllN, xAllE])

# Выводим первые n предсказаний
n = 10
for i in range(n):
  print('Реальное значение - ',np.argmax(yAll[i]), " Предсказанное значение - ", np.argmax(pred[i]))

# Последовательность номеров категорий на реальных данных 
yAll_cat = []
for i in range(len(yAll)):
  yAll_cat.append(np.argmax(yAll[i]))
yAll_cat = np.array(yAll_cat)
print(yAll_cat[:20])

# Последовательность номеров категорий на предсказанных данных 
pred_cat = []
for i in range(len(yAll)):
  pred_cat.append(np.argmax(pred[i]))
pred_cat = np.array(pred_cat)
print(pred_cat[:20])

# Среднеквадратичная ошибка алгоритма на всей базе
print('Model MSE on test data = ', mse(yAll_cat, pred_cat))

# Выведем список неверно предсказаннх категорий
dif_y = []
dif_p = []
for i in range(len(pred_cat)):
  if yAll_cat[i] != pred_cat[i]:
    dif_y.append(yAll_cat[i])
    dif_p.append(pred_cat[i])
print("\n", "Исходные:", dif_y, "\n", "Предсказ:",  dif_p, "\n", "Количество несовпадений:", len(dif_y), "(",round(len(dif_y)/len(pred_cat)*100, 2),"%)", "\n")

# Построение матрицы ошибок
cm = confusion_matrix(yAll_cat,
                      pred_cat,
                      normalize='true')
# Округление значений матрицы ошибок
cm = np.around(cm, 2)

# Отрисовка матрицы ошибок
fig, ax = plt.subplots(figsize=(10, 10))
ax.set_title(f'Матрица ошибок категоризации', fontsize=18)
disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=className)
disp.plot(ax=ax)
plt.gca().images[-1].colorbar.remove()  # Стирание ненужной цветовой шкалы
plt.xlabel('Предсказанные категории', fontsize=16)
plt.ylabel('Верные категории', fontsize=16)
fig.autofmt_xdate(rotation=45)          # Наклон меток горизонтальной оси
plt.show()    

print('\n', '-'*100)

# Для каждого класса:
for cls in range(len(className)):
    # Определяется индекс класса с максимальным значением предсказания
    cls_pred = np.argmax(cm[cls])
    # Выводится текстовая информация о предсказанном классе и значении уверенности
    print('Класс: {:<20} {:3.0f}% сеть отнесла к классу {:<20}'.format(className[cls],
                                                                            100. * cm[cls, cls_pred],
                                                                            className[cls_pred]))

# Средняя точность распознавания определяется как среднее диагональных элементов матрицы ошибок
print('\nСредняя точность распознавания: {:3.1f}%'.format(100. * cm.diagonal().mean()))

# Качество модели по каждому классу отдельно
for i in range(len(className)):
  z_lebel = []
  z_pred = []
  for j in range(len(yAll_cat)):
    if yAll_cat[j] == i:
        z_lebel.append(yAll_cat[j])
        z_pred.append(pred_cat[j])

  precision = precision_score(z_lebel, z_pred, average = 'micro')
  recall = recall_score(z_lebel, z_pred, average = 'micro', zero_division=1)
  f1 = f1_score(z_lebel, z_pred, average = 'micro')
  print('Для класса {:<16} точность = {:.1%}, полнота = {:.1%}'.format(className[i], precision, recall))

print('F1 score = {:.1%}'.format(f1_score(yAll_cat, pred_cat, average = 'micro')))

# Сохраняем обученную модель
model.save('/content/drive/MyDrive/Colab_Notebooks/Diploma/my_best_model.hdf5')

#Загрузаем обученную модель
#model = keras.models.load_model('/content/drive/MyDrive/Colab_Notebooks/Diploma/my_best_model.hdf5')
