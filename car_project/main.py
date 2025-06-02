# app.py
from flask import Flask, request, render_template_string
import re
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

app = Flask(__name__)

# تابع پردازش داده‌ها
def process_messages():
    try:
        with open('messages.txt', 'r', encoding='utf-8') as f:
            messages = f.readlines()
    except FileNotFoundError:
        return pd.DataFrame(), "فایل messages.txt پیدا نشد!"

    cars = []
    for msg in messages:
        try:
            if '||' not in msg:
                continue
            channel, text = msg.split('||', 1)
            car = {'channel': channel.strip(), 'raw_text': text.strip()}

            # فیلتر پیام‌های غیرمرتبط
            if any(keyword in text.lower() for keyword in ['سلام', 'توجه', 'همکاران', 'عید', 'تسلیت']):
                continue

            # برند
            brand_match = re.search(r'(پژو|سمند|تویوتا|هیوندای|کیا|بنز|بی\s*ام\s*و|ام\s*وی\s*ام|جک|چری|رنو|فولکس|نیسان|مزدا|فورد|شورلت|سانتافه)', text, re.IGNORECASE)
            if brand_match:
                car['brand'] = brand_match.group(1).replace(' ', '')

            # تیپ (مدل)
            model_match = re.search(r'(?:[^\n،]*(?:[a-zA-Z0-9\s\-]+)[^\n،]*)', text, re.UNICODE)
            if model_match:
                model = model_match.group(0).strip()
                if car.get('brand'):
                    model = model.replace(car['brand'], '').strip()
                car['model'] = model

            # رنگ
            color_match = re.search(r'(مشکی|سفید|خاکستری|قرمز|آبی|سبز|طلایی|مارون|تیتانیوم|سقف مشکی)', text)
            if color_match:
                car['color'] = color_match.group(1)

            # سال
            year_match = re.search(r'(40[0]|140[0-4]|20[0-2]|[0-9]|9[0-9])', text)
            if year_match:
                year = year_match.group(1)
                if len(year) == 2:
                    car['year'] = int('13' + year)
                elif len(year) == 3:
                    car['year'] = int('14' + year)
                else:
                    car['year'] = int(year)

            # قیمت
            price_match = re.search(r'(\d+\.\d+|\d+|[.,/]\d+|[0-9]\d+|[0-9]\d+\d+)\s*(?:میلیون|تومن|میلیارد)?', text)
            if price_match:
                price = price_match.group(1).replace('/', '').replace(',', '').replace('.', '')
                try:
                    price = float(price)
                    if price < 1:
                        price *= 1000
                    elif price > 1000000:
                        price /= 1000000
                    car['price'] = float(price)
                except ValueError:
                    continue

            # کارکرد
            mileage_match = re.search(r'(\d{1,3}(?:,\d{3})*|\d+)\s*(?:کیلومتر|کارکرد|km)', text, re.IGNORECASE)
            if mileage_match:
                mileage = mileage_match.group(1).replace(',', '')
                car['mileage'] = int(mileage)

            # وضعیت بدنه
            body_match = re.search(r'بدنه\s*(سالم|رنگ\s*شده|تصادفی|تعویض|نیاز به تعمیر)', text, re.IGNORECASE)
            if body_match:
                car['body_condition'] = body_match.group(1)

            # وضعیت شاسی
            chassis_match = re.search(r'شاسی\s*(سالم|تعمیر\s*شده|تعویض|آسیب\s*دیده)', text, re.IGNORECASE)
            if chassis_match:
                car['chassis_condition'] = chassis_match.group(1)

            # وضعیت موتور
            engine_match = re.search(r'موتور\s*(سالم|تعمیر\s*شده|تعویض|نیاز به تعمیر)', text, re.IGNORECASE)
            if engine_match:
                car['engine_condition'] = engine_match.group(1)

            # فقط اگه حداقل برند یا مدل و یکی از قیمت/سال باشه
            if (car.get('brand') or car.get('model')) and (car.get('price') or car.get('year')):
                cars.append(car)
        except Exception as e:
            continue

    df = pd.DataFrame(cars)
    return df, None

# تابع خوشه‌بندی (شبیه API هوش مصنوعی)
def cluster_cars(df):
    df_valid = df.dropna(subset=['year', 'price'])
    if len(df_valid) <= 1:
        df['cluster'] = 'بدون گروه'
        return df

    X = df_valid[['year', 'price']].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    kmeans = KMeans(n_clusters=3, random_state=0).fit(X_scaled)
    df_valid = df_valid.copy()
    df_valid['cluster'] = [f"گروه {i+1} (سال: {int(row['year'])}, قیمت: {int(row['price'])} میلیون)" for i, row in enumerate(df_valid.itertuples())]

    df = df.merge(df_valid[['cluster']], left_index=True, right_index=True, how='left')
    df['cluster'] = df['cluster'].fillna('بدون گروه')
    return df

# پردازش اولیه داده‌ها
df, error = process_messages()
if error:
    print(error)
else:
    df = cluster_cars(df)

# لیست برندها و رنگ‌ها برای فیلتر
brands = sorted(df['brand'].dropna().unique())
colors = sorted(df['color'].dropna().unique())

# قالب HTML با CSS
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>آگهی‌های خودرو</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: 'Vazir', Arial, sans-serif;
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
        @media (max-width: 768px) {
            .filter-form select, .filter-form input {
                width: 100%;
            }
        }
    </style>
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
                <th>قیمت (میلیون)</th>
                <th>کارکرد (کیلومتر)</th>
                <th>وضعیت بدنه</th>
                <th>وضعیت شاسی</th>
                <th>وضعیت موتور</th>
                <th>گروه</th>
            </tr>
            {% for car in cars %}
            <tr>
                <td>{{ car.channel|default('نامشخص') }}</td>
                <td>{{ car.brand|default('نامشخص') }}</td>
                <td>{{ car.model|default('نامشخص') }}</td>
                <td>{{ car.color|default('نامشخص') }}</td>
                <td>{{ car.year|default('نامشخص') }}</td>
                <td>{{ car.price|default('نامشخص') }}</td>
                <td>{{ car.mileage|default('نامشخص') }}</td>
                <td>{{ car.body_condition|default('نامشخص') }}</td>
                <td>{{ car.chassis_condition|default('نامشخص') }}</td>
                <td>{{ car.engine_condition|default('نامشخص') }}</td>
                <td>{{ car.cluster|default('بدون گروه') }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
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

    return render_template_string(HTML_TEMPLATE, cars=filtered.to_dict('records'), brands=brands, colors=colors)

if __name__ == '__main__':
    app.run(debug=True)