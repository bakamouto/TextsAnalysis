import json
import tiktoken
import datetime as dt
import openai
from pathlib import Path


def get_key(file_name):
    with open(file_name, "r") as key_file:
        line = key_file.read().strip("\n")
        return line


def get_encoding(model='gpt-4'):
    return tiktoken.encoding_for_model(model)


def count_text_tokens(text: str | list, model='gpt-4'):
    encoding = get_encoding(model)
    if isinstance(text, str):
        return len(encoding.encode(text))
    return sum(len(encoding.encode(m)) for m in text)


def get_sets_of_messages(data, time_delta=60, date1=dt.date(2018, 7, 1), date2=dt.date(2018, 8, 1), max_tokens=1500):
    raw_divisions = []
    current = []
    for index in range(len(data))[1:]:
        if dt.date.fromtimestamp(data[index]["timestamp"]) > date1:
            if data[index]["timestamp"] - data[index - 1]["timestamp"] > time_delta and len(current) > 0:
                raw_divisions.append(current)
                if dt.date.fromtimestamp(data[index]["timestamp"]) > date2:  # until august 1 2018
                    break
                current = []
            else:
                current.append(data[index])

    divisions = []
    token_length = 0
    current_set = []
    for message_set in raw_divisions:
        new_tokens = count_text_tokens([message["text"] for message in message_set])
        if token_length == 0:
            token_length = new_tokens
            current_set = message_set[::]
        elif max_tokens < token_length + new_tokens:
            token_length = 0
            divisions.append(current_set[::])
            current_set = []
        elif token_length < max_tokens:
            token_length += new_tokens
            current_set.extend(message_set[::])

    for i in range(len(divisions)):
        for j in range(len(divisions[i])):
            message = divisions[i][j]["text"]
            while '[' in message and ']' in message and '|' in message:
                left_bracket = message.find("[")
                division = message.find('|')
                right_bracket = message.find("]")
                before = message[:left_bracket]
                after = message[right_bracket + 1:]
                between = message[division + 1: right_bracket]
                message = before + between + after
                divisions[i][j]["text"] = message

    return divisions


def get_summary_by_groups(groups, save_file_name, api_key):
    openai.api_key = api_key

    result = []
    for message_set in groups:
        request = "На русском языке напиши, какие темы обсуждаются в этих сообщениях: \n" + '\n'.join([message["text"] for message in message_set])

        response = openai.ChatCompletion.create(
            model='gpt-4',
            messages=[{"role": "user", "content": request}],
            max_tokens=1500
        )

        result.append(
            {
                "start_timestamp": message_set[0]["timestamp"],
                "stop_timestamp": message_set[-1]["timestamp"],
                "summary": response.choices[0].message.content
            }
        )

    with open(save_file_name, "w", encoding="utf-8") as new_file:
        json.dump(result, new_file)


def summarise_by_month(data_file_name, delta, tokens, directory):
    with open(data_file_name, encoding="utf-8") as file:
        data = json.load(file)
        data = sorted(data, key=lambda a: a["timestamp"])

        start_date = dt.date.fromtimestamp(data[0]["timestamp"]).replace(day=1)
        start_date = start_date.replace(month=start_date.month + 1)
        end_date = dt.date.fromtimestamp(data[-1]["timestamp"]).replace(day=1)
        end_date = end_date.replace(month=end_date.month + 1)

        while start_date < end_date:

            date1 = start_date
            year = date1.year
            month = date1.month
            date2 = start_date
            if month == 12:
                date2 = date2.replace(month=1, year=year+1)
            else:
                date2 = date2.replace(month=month+1)

            texts = get_sets_of_messages(data, delta, date1, date2, tokens)
            get_summary_by_groups(texts, f"{directory}/summary_{year}_{month}.json", get_key("key.txt"))

            start_date = date2


def summarise_months(directory, save_file_name, api_key):
    result = []
    files = Path(directory).glob('*')
    files = sorted(files, key=lambda a: int(a.name.rstrip(".json").lstrip("summary_")[5:]))
    for file in files:
        year, month = file.name.rstrip(".json").lstrip("summary_").split('_')
        with open(directory + '/' + file.name, "r", encoding="utf-8") as current_file:
            openai.api_key = api_key
            data = json.load(current_file)

            text = ' '.join([entry["summary"] for entry in data])
            if count_text_tokens(text) > 3000:
                request1 = "На русском языке напиши, какие темы есть в этом тексте: " + \
                           ' '.join([entry["summary"] for entry in data[:len(data) // 2]])
                request2 = "На русском языке напиши, какие темы есть в этом тексте: " + \
                           ' '.join([entry["summary"] for entry in data[len(data) // 2:]])
                response1 = openai.ChatCompletion.create(
                    model='gpt-4',
                    messages=[{"role": "user", "content": request1}],
                    max_tokens=1500
                )
                response2 = openai.ChatCompletion.create(
                    model='gpt-4',
                    messages=[{"role": "user", "content": request2}],
                    max_tokens=1500
                )
                summary1 = response1.choices[0].message.content
                summary2 = response2.choices[0].message.content
                final_summary = openai.ChatCompletion.create(
                    model='gpt-4',
                    messages=[{"role": "user",
                               "content": 'На русском языке напиши, какие темы есть в этом тексте: ' + summary1 + " " + summary2}],
                    max_tokens=1500
                ).choices[0].message.content
                result.append(
                    {
                        "summary": final_summary,
                        "year": year,
                        "month": month
                    }
                )
            else:
                request = "На русском языке напиши, какие темы есть в этом тексте: " + ' '.join([entry["summary"] for entry in data])
                response = openai.ChatCompletion.create(
                    model='gpt-4',
                    messages=[{"role": "user", "content": request}],
                    max_tokens=1500
                )
                summary = response.choices[0].message.content
                result.append(
                    {
                        "summary": summary,
                        "year": year,
                        "month": month
                    }
                )

    with open(save_file_name, "w", encoding="utf-8") as save_file:
        json.dump(result, save_file)
