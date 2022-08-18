from bs4 import BeautifulSoup as bf
from urllib.request import urlopen
from prettytable import PrettyTable as pt
from nltk.corpus import wordnet

PREFIX = "https://www.prospects.ac.uk"
html = urlopen("https://www.prospects.ac.uk/careers-advice/what-can-i-do-with-my-degree")
obj = bf(html.read(), 'html.parser')
url_list = []
degree_list = []
for i in obj.body.div.find_next_sibling("div").main.div.find_next_sibling("div").div.div.div.ul.children:
   url_list.append(PREFIX + i.a.attrs["href"])
   degree_list.append(i.a.div.div.p.string)

for i in degree_list:
    print(i)
    synonyms = []
    for i in wordnet.synsets(i.replace(" ","_")):
        for j in i.lemmas():
            synonyms.append(j.name())
    print(list(set(synonyms)))

with open("degree_list.txt", 'w') as f:
    for i in degree_list:
        f.write(i + "\n")
exit()

for i in url_list:
    html = urlopen(i)
    obj = bf(html.read(), 'html.parser')
    q_a_list = []
    job_name = obj.body.div.find_next_sibling("div").main.article.div.div.div.div.div.header.h1.string
    pair = [job_name, ""]
    answer = ""
    for j in obj.body.div.find_next_sibling("div").main.article.section.div.div.div.find_next_sibling("div").div.children:
        if j.name == "footer": break
        if j.name == "h2":
            pair[1] = answer
            q_a_list.append(pair)
            pair = [j.string, ""]
            answer = ""
        elif j.name == "p":
            answer += "".join(j.strings)
            answer += "\n"
        elif j.name == "ul":
            for k in j.children:
                if k.name == "li":
                    answer += "* "
                    answer += "".join(j.strings)
                    answer += "\n"
        elif j.name == "figure":
            if "content-table" in j.attrs["class"]:
                table = j.div.table
                caption = "".join(j.figcaption.strings)
                thead = table.thead
                tbody = table.tbody
                field = []
                tb = pt()
                tb.align = "l"
                for th in thead.tr.children:
                    if th.name == "th":
                        field.append("".join(th.strings))
                tb.field_names = field
                for tr in tbody.children:
                    if tr.name == "tr":
                        row = []
                        for td in tr.children:
                            if td.name == "td":
                                row.append("".join(td.strings))
                        tb.add_row(row)
                answer += caption + "\n"
                answer += tb.get_string()
    pair[1] = answer
    q_a_list.append(pair)
print(q_a_list)