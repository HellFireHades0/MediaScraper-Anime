import threading
from bs4 import BeautifulSoup
import requests
import fake_useragent
import subprocess
import base64
import json
import lxml.html as htmlparser
import re
import yarl
from Cryptodome.Cipher import AES
import youtube_dl.utils


headers = {'user-agent': fake_useragent.UserAgent().random}
anime_name = input('Enter Anime Name: ').replace(' ', '%20')
soup = BeautifulSoup(requests.get('https://gogoanime.fi//search.html?keyword=' + anime_name).text, 'html.parser')
count = 0
all_url, ep_num = [], []
for k, i in enumerate(soup.find_all('a')):
    if str(i.get('href')).startswith('/category') and k % 2 == 0:
        count += 1
        print('[' + str(count) + ']', str(i.get('href'))[10:].replace('-', ' '))
        all_url.append('https://gogoanime.fi/' + str(i.get('href')))

number = int(input('Enter number: '))
soup1 = BeautifulSoup(requests.get(f'https://gogoanime.fi/category/{all_url[number - 1][31:]}',
                                   headers=headers).text, 'html.parser')
headers = {'user-agent': fake_useragent.UserAgent().random}
for i in soup1.find_all('a', ep_end=True, ep_start=True):
    ep_num.append(int(i.get('ep_start')))
    ep_num.append(int(i.get('ep_end')))
episode_number = ''
if min(ep_num) + 1 == max(ep_num):
    episode_number = 1
else:
    episode_number = input(f'Enter Episode Number between {min(ep_num)+1}-{max(ep_num)}: ')
soup2 = BeautifulSoup(requests.get(f'https://gogoanime.fi/{all_url[number - 1][31:]}-episode-{episode_number}',
                                   headers=headers).text, 'html.parser')

gogoanime_secret = b"25716538522938396164662278833288"
gogoanime_iv = b"1285672985238393"
custom_padder = "\x08\x0e\x03\x08\t\x03\x04\t"


def get_quality(url_text):
    match = re.search(r"(\d+) P", url_text)
    if not match:
        return None
    return int(match.group(1))


def pad(data):
    return data + custom_padder[(len(custom_padder) - len(data) % 16):]


def aes_encrypt(data: str):
    return base64.b64encode(
        AES.new(gogoanime_secret, AES.MODE_CBC, iv=gogoanime_iv).encrypt(
            pad(data).encode()))


def aes_decrypt(data: str):
    return AES.new(gogoanime_secret, AES.MODE_CBC, iv=gogoanime_iv).decrypt(
        base64.b64decode(data))


def extract(url):
    content_info = aes_decrypt(
        htmlparser.fromstring(requests.get(url).text).cssselect('[data-name="crypto"]')[0].get("data-value"))
    content_id = content_info[: content_info.index(b"&")].decode()

    parsed_url = yarl.URL(url)
    next_host = "https://{}/".format(parsed_url.host)


    response = requests.get(
        "{}encrypt-ajax.php".format(next_host),
        params={"id": aes_encrypt(content_id).decode()},
        headers={"x-requested-with": "XMLHttpRequest"},
    )
    content = json.loads(
        aes_decrypt(response.json().get("data")).replace(b'o"<P{#meme":', b'e":[{"file":').decode("utf-8")
        .strip("\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10")
    )

    def yielder():
        for origin in content.get("source"):
            yield {
                "stream_url": origin.get("file"),
                "quality": get_quality(origin.get("label", "")),
                "headers": {"referer": next_host},
            }

        for backups in content.get("source_bk"):
            yield {
                "stream_url": backups.get("file"),
                "quality": get_quality(origin.get("label", "")),
                "headers": {"referer": next_host},
            }


    return list(yielder())


qualities = [f"{str(i['quality'])}p" for i in extract(f"https:{soup2.find('iframe')['src']}")
             if str(i['quality']) != 'None']
quality = str(input(f"Enter Quality:[{', '.join(qualities)}]: "))
download = input('Download Current Episode [Y/N]: ')


def run():
    subprocess.run(f'mpv --referrer="{i["headers"]["referer"]}" --force-media-title="'
                   f'{all_url[number - 1][31:] + episode_number}" "{stream_url}"')

for i in extract(url=f"https:{soup2.find('iframe')['src']}"):
    if str(i['quality']) == str(quality[:-1]):
        stream_url = i["stream_url"]

youtube_dl.utils.std_headers['Referer'] = extract(f"https:{soup2.find('iframe')['src']}")[0]["headers"]["referer"]
if download.lower() == 'y':
    with youtube_dl.YoutubeDL({'outtmpl': f"{all_url[number - 1][31:]}ep-number{episode_number}"}) as ydl:
        ydl.download([stream_url])
else:
    threading.Thread(target=run).start()
