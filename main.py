# main.py
from flask import Flask, request, render_template_string
import re
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
import asyncio
import nest_asyncio
import os
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
import pickle

os.environ["LOKY_MAX_CPU_COUNT"] = "4"
nest_asyncio.apply()

app = Flask(__name__)

# تنظیمات تلگرام
API_ID =
API_HASH = 
PHONE = 
channel_list = 

# بارگذاری مدل زبان فارسی spaCy
nlp = spacy.load("fa_core_news_sm")

# دیتاست ساده برای ترینیگ دسته‌بندی کانال‌ها
training_data = [
    ("۲۰۷ پانا ارتقا مشکی ۱۴۰۴ برج روز ۹۲۶/۰۰۰", "مرتبط"),  # پیام خودرو
    ("جک j4 مشکی ۱۴۰۴ برج ۲ ۹۶۲/۰۰۰", "مرتبط"),
    ("فیدلیتی پرستیژ ۵ نفره داخل طوسی ۱۴۰۳ ۳/۱۲۴/۰۰۰", "مرتبط"),
    ("سلام دوستان، امروز می‌خوام درباره آشپزی حرف بزنم", "غیرمرتبط"),  # پیام غیرمرتبط
    ("فروش گوشی سامسونگ مدل A52 قیمت ۵ میلیون", "غیرمرتبط"),
]

# آماده‌سازی داده‌های ترینیگ
texts, labels = zip(*training_data)
vectorizer = TfidfVectorizer()
X_train = vectorizer.fit_transform(texts)
y_train = labels

# ترینیگ مدل SVM
classifier = SVC(kernel='linear')
classifier.fit(X_train, y_train)

# ذخیره مدل و vectorizer برای استفاده بعدی
with open('channel_classifier.pkl', 'wb') as f:
    pickle.dump(classifier, f)
with open('vectorizer.pkl', 'wb') as f:
    pickle.dump(vectorizer, f)

# تابع برای فرمت کردن قیمت
def format_price(price):
    if pd.isna(price) or price is None:
        return "بدون اطلاعات"
    price = int(price)
    price_str = f"{price:,}".replace(",", ".")
    return f"{price_str} تومن"

# تابع اعتبارسنجی داده‌ها
def validate_data(car):
    status = "درست"
    
    if 'year' in car and not pd.isna(car['year']):
        year = car['year']
        if not (1370 <= year <= 1404 or 2000 <= year <= 2025):
            status = "مشکوک: سال خارج از محدوده (1370-1404 یا 2000-2025)"

    if 'price' in car and not pd.isna(car['price']):
        price = car['price']
        if not (50 <= price <= 10000):
            status = "مشکوک: قیمت خارج از محدوده (50M-10B)"

    if 'brand' in car and 'model' in car and not pd.isna(car['brand']) and not pd.isna(car['model']):
        brand = car['brand'].lower()
        model = car['model'].lower()
        valid_models = {
            'پراید': ['111', '131', '132', '151'],
            'دنا': ['پلاس', 'توربو', 'پلاس توربو 6 دنده'],
            '207': ['پانا', 'پانامرا', 'تیپ'],
            'دیگنیتی': ['پرایم'],
            'جک': ['j4', 'j7'],
            'فیدلیتی': ['پرستیژ', 'داخل طوسی 5 نفره'],
            'سورن': ['پلاس'],
            'تارا': ['اتومات v4 تیتانیوم'],
            'تویوتا': ['لوین 1200']
        }
        if brand in valid_models and not any(m in model for m in valid_models[brand]):
            status = "مشکوک: مدل با برند تطابق ندارد"

    if 'mileage' in car and not pd.isna(car['mileage']):
        mileage = car['mileage']
        if not (0 <= mileage <= 500000):
            status = "مشکوک: کارکرد خارج از محدوده (0-500K)"

    return status

# تابع تشخیص کانال مرتبط
def is_relevant_channel(message):
    with open('vectorizer.pkl', 'rb') as f:
        vectorizer = pickle.load(f)
    with open('channel_classifier.pkl', 'rb') as f:
        classifier = pickle.load(f)
    message_vector = vectorizer.transform([message])
    prediction = classifier.predict(message_vector)
    return prediction[0] == "مرتبط"

# تابع گرفتن پیام‌ها از تلگرام
async def fetch_messages():
    async with TelegramClient('session', API_ID, API_HASH) as client:
        await client.start(phone=PHONE)
        messages = []
        for channel in channel_list:
            try:
                entity = await client.get_entity(channel)
                history = await client(GetHistoryRequest(
                    peer=entity,
                    limit=100,
                    offset_id=0,
                    offset_date=None,
                    add_offset=0,
                    max_id=0,
                    min_id=0,
                    hash=0
                ))
                for msg in history.messages:
                    if msg.message:
                        # فقط پیام‌های مرتبط رو اضافه کن
                        if is_relevant_channel(msg.message):
                            messages.append(f"{channel}||{msg.message}")
                print(f"تعداد پیام‌های گرفته‌شده از {channel}: {len(history.messages)}")
            except Exception as e:
                print(f"خطا در گرفتن پیام‌ها از {channel}: {e}")
                continue
        return messages

# تابع پردازش داده‌ها با spaCy
def process_messages(messages):
    print(f"تعداد کل پیام‌های دریافتی: {len(messages)}")
    cars = []
    for msg in messages:
        try:
            if '||' not in msg:
                continue
            channel, text = msg.split('||', 1)
            car = {'channel': channel.strip(), 'raw_text': text.strip()}

            # استفاده از spaCy برای استخراج اطلاعات
            doc = nlp(text)

            # برند و مدل (بهبود با spaCy)
            brand = None
            model = None
            for ent in doc.ents:
                if ent.label_ == "PRODUCT":  # spaCy ممکنه برند رو به‌عنوان PRODUCT تشخیص بده
                    brand = ent.text
                elif ent.label_ == "ORG":
                    brand = ent.text
            # اگر spaCy برند رو پیدا نکرد، از regex قبلی استفاده کن
            if not brand:
                brand_match = re.search(r'(دیگنیتی|پراید|دنا|پژو|سمند|تویوتا|هیوندای|کیا|بنز|بی\s*ام\s*و|ام\s*وی\s*ام|جک|چری|رنو|فولکس|نیسان|مزدا|فورد|شورلت|سانتافه|207|پانا|فیدلیتی|سورن|ری\s*را|تارا)', text, re.IGNORECASE)
                if brand_match:
                    brand = brand_match.group(1).replace(' ', '')
            car['brand'] = brand

            # مدل
            model_match = re.search(r'(?:' + (car.get('brand', '') or '') + r'\s*)([\w\s\d\-]+?)(?=\s*(?:داخل|رنگ|سفید|مشکی|طوسی|سال|مدل|قیمت|میلیون|تومن|کارکرد|بدنه|شاسی|موتور|$))', text, re.UNICODE)
            if model_match:
                model = model_match.group(1).strip()
                if car.get('brand'):
                    model = model.replace(car['brand'], '').strip()
                extra_info = re.search(r'(داخل\s*\w+\s*\d*\s*نفره?)', text, re.UNICODE)
                if extra_info:
                    model = f"{model} {extra_info.group(1).strip()}" if model else extra_info.group(1).strip()
                if car.get('brand') == '207' and 'پانا' in model.lower():
                    model = 'پانامرا'
            car['model'] = model

            # رنگ
            color_match = re.search(r'(رنگ\s+)?(?:مشکی|سفید|خاکستری|قرمز|آبی|سبز|طلایی|مارون|تیتانیوم|سقف مشکی)', text)
            if color_match:
                car['color'] = color_match.group(0).replace('رنگ ', '').strip()
            else:
                car['color'] = "بدون اطلاعات"

            # سال
            year_match = re.search(r'(?:سال|مدل)\s*(140[0-4]|13[9-9][0-9]|20[0-2][0-9])', text)
            if year_match:
                year = year_match.group(1)
                car['year'] = int(year)
            else:
                year_match = re.search(r'(140[0-4]|13[9-9][0-9]|20[0-2][0-9])(?=\s*برج|\s|$|[^\d])', text)
                if year_match and not re.search(r'(?:قیمت|تومان)\s*' + year_match.group(1), text):
                    car['year'] = int(year_match.group(1))

            # قیمت
            price_match = re.search(r'(?:\bقیمت\s*)?(\d+[./]\d+[./]\d+|\d{3,})(?:\s*(?:تومان|میلیون|تومن|میلیارد))?', text)
            if price_match:
                price = price_match.group(1).replace('/', '').replace('.', '').replace(',', '')
                try:
                    price = float(price)
                    if price < 10:
                        price *= 1000
                    elif 10 <= price <= 100:
                        price *= 1000
                    elif 100 < price <= 1000:
                        price = price
                    elif price > 1000000:
                        price /= 1000000
                    car['price'] = float(price)
                except ValueError:
                    car['price'] = None

            # کارکرد
            mileage_match = re.search(r'(\d{1,3}(?:,\d{3})*|\d+)\s*(?:کیلومتر|کارکرد|km)', text, re.IGNORECASE)
            if mileage_match:
                mileage = mileage_match.group(1).replace(',', '')
                car['mileage'] = int(mileage)

            # وضعیت بدنه
            body_match = re.search(r'بدنه\s*(سالم|رنگ\s*شده|تصادفی|تعویض|نیاز به تعمیر)', text, re.IGNORECASE)
            if body_match:
                car['body_condition'] = body_match.group(1)
            else:
                car['body_condition'] = "بدون اطلاعات"

            # وضعیت شاسی
            chassis_match = re.search(r'شاسی\s*(سالم|تعمیر\s*شده|تعویض|آسیب\s*دیده)', text, re.IGNORECASE)
            if chassis_match:
                car['chassis_condition'] = chassis_match.group(1)
            else:
                car['chassis_condition'] = "بدون اطلاعات"

            # وضعیت موتور
            engine_match = re.search(r'موتور\s*(سالم|تعمیر\s*شده|تعویض|نیاز به تعمیر)', text, re.IGNORECASE)
            if engine_match:
                car['engine_condition'] = engine_match.group(1)
            else:
                car['engine_condition'] = "بدون اطلاعات"

            if (car.get('brand') or car.get('model')) and (car.get('year') or car.get('price') is not None):
                car['status'] = validate_data(car)
                cars.append(car)
        except Exception as e:
            print(f"خطا در پردازش پیام: {e}")
            continue

    print(f"تعداد آگهی‌های پردازش‌شده: {len(cars)}")
    df = pd.DataFrame(cars)
    if 'price' not in df.columns:
        df['price'] = None
    return df, None

# تابع خوشه‌بندی
def cluster_cars(df):
    if 'year' not in df.columns or 'price' not in df.columns:
        df['cluster'] = 'بدون گروه'
        return df

    df_valid = df.dropna(subset=['year', 'price'])
    if len(df_valid) <= 1:
        df['cluster'] = 'بدون گروه'
        return df

    X = df_valid[['year', 'price']].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    kmeans = KMeans(n_clusters=3, random_state=0).fit(X_scaled)
    labels = kmeans.labels_

    df_valid = df_valid.copy()
    df_valid['label'] = labels
    cluster_summary = df_valid.groupby('label').agg({'year': 'mean', 'price': 'mean'}).reset_index()

    cluster_labels = []
    for label in range(3):
        year_mean = int(cluster_summary.loc[cluster_summary['label'] == label, 'year'].iloc[0])
        price_mean = int(cluster_summary.loc[cluster_summary['label'] == label, 'price'].iloc[0])
        if year_mean >= 1402 and price_mean > 1500:
            cluster_labels.append("ماشین‌های جدید و گران")
        elif year_mean <= 1398:
            cluster_labels.append("ماشین‌های قدیمی و ارزان")
        else:
            cluster_labels.append("ماشین‌های متوسط")

    df_valid['cluster'] = [cluster_labels[label] for label in labels]
    df = df.merge(df_valid[['cluster']], left_index=True, right_index=True, how='left')
    df['cluster'] = df['cluster'].fillna('بدون گروه')
    return df

# قالب HTML با CSS و رفرش خودکار
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>آگهی‌های خودرو</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            direction: rtl;
            background-color: #f5f5f5;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        h1 {
            color: #d32f2f;
            text-align: center;
            margin-bottom: 20px;
        }
        .filter-form {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin-bottom: 30px;
            padding: 20px;
            background-color: #fafafa;
            border-radius: 8px;
        }
        .filter-form label {
            font-weight: bold;
            color: #333;
        }
        .filter-form select, .filter-form input[type="text"], .filter-form input[type="number"] {
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            width: 150px;
            font-size: 14px;
        }
        .filter-form input[type="submit"] {
            background-color: #d32f2f;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
        }
        .filter-form input[type="submit"]:hover {
            background-color: #b71c1c;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 12px;
            text-align: right;
            font-size: 14px;
        }
        th {
            background-color: #d32f2f;
            color: white;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        tr:hover {
            background-color: #f1f1f1;
        }
        tr[status*="مشکوک"] {
            background-color: #ffebee;
        }
        @media (max-width: 768px) {
            .filter-form select, .filter-form input {
                width: 100%;
            }
        }
    </style>
    <script>
        setInterval(function() {
            location.reload();
        }, 300000);
    </script>
</head>
<body>
    <div class="container">
        <h1>آگهی‌های خودرو</h1>
        <form class="filter-form" method="POST">
            <label>برند:</label>
            <select name="brand">
                <option value="">همه</option>
                {% for brand in brands %}
                <option value="{{ brand }}">{{ brand }}</option>
                {% endfor %}
            </select>
            <label>تیپ:</label>
            <input type="text" name="model" placeholder="مثال: 206 تیپ 2">
            <label>رنگ:</label>
            <select name="color">
                <option value="">همه</option>
                {% for color in colors %}
                <option value="{{ color }}">{{ color }}</option>
                {% endfor %}
            </select>
            <label>حداقل قیمت (میلیون):</label>
            <input type="number" name="min_price" value="0">
            <label>حداکثر قیمت (میلیون):</label>
            <input type="number" name="max_price" value="10000">
            <label>حداقل سال:</label>
            <input type="number" name="min_year" value="0">
            <label>حداکثر سال:</label>
            <input type="number" name="max_year" value="1404">
            <label>حداکثر کارکرد (کیلومتر):</label>
            <input type="number" name="max_mileage" value="1000000">
            <label>وضعیت بدنه:</label>
            <select name="body_condition">
                <option value="">همه</option>
                <option value="سالم">سالم</option>
                <option value="رنگ شده">رنگ‌شده</option>
                <option value="تصادفی">تصادفی</option>
            </select>
            <label>وضعیت شاسی:</label>
            <select name="chassis_condition">
                <option value="">همه</option>
                <option value="سالم">سالم</option>
                <option value="تعمیر شده">تعمیر‌شده</option>
            </select>
            <label>وضعیت موتور:</label>
            <select name="engine_condition">
                <option value="">همه</option>
                <option value="سالم">سالم</option>
                <option value="تعمیر شده">تعمیر‌شده</option>
            </select>
            <input type="submit" value="فیلتر کن">
        </form>
        <h2>نتایج:</h2>
        <table>
            <tr>
                <th>کانال</th>
                <th>برند</th>
                <th>تیپ</th>
                <th>رنگ</th>
                <th>سال</th>
                <th>قیمت</th>
                <th>کارکرد (کیلومتر)</th>
                <th>وضعیت بدنه</th>
                <th>وضعیت شاسی</th>
                <th>وضعیت موتور</th>
                <th>گروه</th>
                <th>وضعیت</th>
            </tr>
            {% for car in cars %}
            <tr status="{{ car.status }}">
                <td>{{ car.channel|default('بدون اطلاعات') }}</td>
                <td>{{ car.brand|default('بدون اطلاعات') }}</td>
                <td>{{ car.model|default('بدون اطلاعات') }}</td>
                <td>{{ car.color|default('بدون اطلاعات') }}</td>
                <td>{{ car.year|default('بدون اطلاعات') }}</td>
                <td>{{ format_price(car.price) }}</td>
                <td>{{ car.mileage|default('بدون اطلاعات') }}</td>
                <td>{{ car.body_condition|default('بدون اطلاعات') }}</td>
                <td>{{ car.chassis_condition|default('بدون اطلاعات') }}</td>
                <td>{{ car.engine_condition|default('بدون اطلاعات') }}</td>
                <td>{{ car.cluster|default('بدون گروه') }}</td>
                <td>{{ car.status|default('درست') }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        messages = loop.run_until_complete(fetch_messages())
        loop.close()
    except Exception as e:
        print(f"خطا در گرفتن پیام‌ها: {e}")
        messages = []

    df, error = process_messages(messages)
    if error:
        print(error)
    else:
        df = cluster_cars(df)

    brands = sorted(df['brand'].dropna().unique()) if not df.empty else []
    colors = sorted(df['color'].dropna().unique()) if not df.empty else []

    filtered = df
    if request.method == 'POST':
        brand = request.form.get('brand')
        model = request.form.get('model')
        color = request.form.get('color')
        min_price = float(request.form.get('min_price', 0))
        max_price = float(request.form.get('max_price', float('inf')))
        min_year = int(request.form.get('min_year', 0))
        max_year = int(request.form.get('max_year', 9999))
        max_mileage = float(request.form.get('max_mileage', float('inf')))
        body_condition = request.form.get('body_condition')
        chassis_condition = request.form.get('chassis_condition')
        engine_condition = request.form.get('engine_condition')

        if brand:
            filtered = filtered[filtered['brand'] == brand]
        if model:
            filtered = filtered[filtered['model'].str.contains(model, case=False, na=False)]
        if color:
            filtered = filtered[filtered['color'] == color]
        filtered = filtered[
            (filtered['price'].fillna(float('inf')) >= min_price) &
            (filtered['price'].fillna(float('inf')) <= max_price) &
            (filtered['year'].fillna(0) >= min_year) &
            (filtered['year'].fillna(0) <= max_year) &
            (filtered['mileage'].fillna(float('inf')) <= max_mileage)
        ]
        if body_condition:
            filtered = filtered[filtered['body_condition'] == body_condition]
        if chassis_condition:
            filtered = filtered[filtered['chassis_condition'] == chassis_condition]
        if engine_condition:
            filtered = filtered[filtered['engine_condition'] == engine_condition]

    return render_template_string(HTML_TEMPLATE, cars=filtered.to_dict('records'), brands=brands, colors=colors, format_price=format_price)

if __name__ == '__main__':
    app.run(debug=True)
