# app.py
from flask import Flask, request, render_template_string
import pandas as pd
from process_data import process_messages, cluster_cars

app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>لیست ماشین‌ها</title>
    <meta charset="UTF-8">
</head>
<body>
    <h1>فیلتر ماشین‌ها</h1>
    <form method="POST">
        <label>حداکثر قیمت (میلیون):</label>
        <input type="number" name="max_price" value="10000"><br>
        <label>حداقل سال:</label>
        <input type="number" name="min_year" value="0"><br>
        <input type="submit" value="فیلتر کن">
    </form>
    <h2>نتایج:</h2>
    <table border="1">
        <tr>
            <th>کانال</th>
            <th>مدل</th>
            <th>گروه مدل</th>
            <th>رنگ</th>
            <th>سال</th>
            <th>قیمت (میلیون)</th>
            <th>شماره تماس</th>
        </tr>
        {% for car in cars %}
        <tr>
            <td>{{ car.channel }}</td>
            <td>{{ car.model|default('نامشخص') }}</td>
            <td>{{ car.cluster|default('بدون گروه') }}</td>
            <td>{{ car.color|default('نامشخص') }}</td>
            <td>{{ car.year|default('نامشخص') }}</td>
            <td>{{ car.price|default('نامشخص') }}</td>
            <td>{{ car.phone|default('نامشخص') }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
'''

df = process_messages()
df = cluster_cars(df)

@app.route('/', methods=['GET', 'POST'])
def index():
    filtered = df
    if request.method == 'POST':
        max_price = float(request.form.get('max_price', 10000))
        min_year = int(request.form.get('min_year', 0))
        filtered = df[(df['price'].fillna(float('inf')) <= max_price) & (df['year'].fillna(0) >= min_year)]
    return render_template_string(HTML_TEMPLATE, cars=filtered.to_dict('records'))

if __name__ == '__main__':
    app.run(debug=True)