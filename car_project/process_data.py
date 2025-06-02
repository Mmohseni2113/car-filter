# process_data.py
import re
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

def process_messages():
    try:
        with open('messages.txt', 'r', encoding='utf-8') as f:
            messages = f.readlines()
    except FileNotFoundError:
        print("فایل messages.txt پیدا نشد!")
        return pd.DataFrame()

    cars = []
    for msg in messages:
        try:
            if '||' not in msg:
                continue
            channel, text = msg.split('||', 1)
            car = {'channel': channel.strip()}
            
            # مدل: اولین عبارت قبل از کاما یا خط جدید
            model_match = re.search(r'^([^\n،]+)', text)
            if model_match:
                car['model'] = model_match.group(1).strip()
            
            # رنگ: کلمات مشخص
            color_match = re.search(r'(مشکی|سفید|خاکستری|قرمز|آبی|سبز|طلایی|مارون|تیتانیوم)', text)
            if color_match:
                car['color'] = color_match.group(1)
            
            # سال: ۴۰۴ یا 1404 یا اعداد چهار رقمی
            year_match = re.search(r'(40[0-4]|140[0-4]|[0-2]\d{3})', text)
            if year_match:
                year = year_match.group(1)
                car['year'] = int(year) if len(year) == 4 else int('14' + year)
            
            # قیمت: فرمت‌های مختلف (1.590، 2/090/000/000، 948000000)
            price_match = re.search(r'(\d+[.,/]\d+|\d+[.,/]\d+[.,/]\d+|\d+)\s*(?:میلیون|تومن|میلیارد)?', text)
            if price_match:
                price = price_match.group(1).replace('/', '').replace(',', '').replace('.', '')
                try:
                    price = float(price)
                    if price < 10:  # فرضاً 1.590 یعنی 1590 میلیون
                        price *= 1000
                    car['price'] = int(price)
                except ValueError:
                    car['price'] = None
            
            # شماره تماس: 09xxxxxxxxx
            phone_match = re.search(r'09\d{9}', text)
            if phone_match:
                car['phone'] = phone_match.group(0)
            
            # فقط اگه مدل یا قیمت باشه اضافه کن
            if car.get('model') or car.get('price'):
                cars.append(car)
        except Exception as e:
            print(f"خطا در پردازش: {msg.strip()} - {e}")
            continue

    df = pd.DataFrame(cars)
    df.to_csv('cars_data.csv', index=False, encoding='utf-8-sig')
    return df

def cluster_cars(df):
    df_with_model = df.dropna(subset=['model'])
    if len(df_with_model) == 0:
        df['cluster'] = 'بدون گروه'
        return df
    
    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(df_with_model['model'])
    kmeans = KMeans(n_clusters=min(5, len(df_with_model)), random_state=0).fit(X)
    clusters = kmeans.labels_
    
    df_with_model = df_with_model.copy()
    df_with_model['cluster'] = [f"گروه {i}" for i in clusters]
    df = df.merge(df_with_model[['cluster']], left_index=True, right_index=True, how='left')
    df['cluster'] = df['cluster'].fillna('بدون گروه')
    return df

if __name__ == '__main__':
    df = process_messages()
    df = cluster_cars(df)
    print(df.head())