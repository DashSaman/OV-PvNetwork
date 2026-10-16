"""Hostile node labels must remain inert HTML data, never handler source."""
from html.parser import HTMLParser
from pathlib import Path
import unittest
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT=Path(__file__).resolve().parents[1]
LABEL="');globalThis.pvnDemoXss=1;//"
URL='https://demo.example.invalid/sub/download/demo-user/'+LABEL


def render_fixture():
    environment=Environment(loader=FileSystemLoader(ROOT/'frontend/templates'),
                            autoescape=select_autoescape(['html']))
    return environment.get_template('subscription.html').render(
        name='demo-user',is_active=True,total=1000,used=100,expiry_date='2030-01-01',
        device_limit=1,anyconnect=None,ovpn_download_links={LABEL:URL},
        node_health={LABEL:{'recommended':True,'online':True,'load':10,'mbps':1,
                           'flag':'Demo','state':'normal','state_fa':'Demo'}})


class QrParser(HTMLParser):
    def __init__(self):super().__init__();self.buttons=[]
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if 'node-qr' in values.get('class','').split():self.buttons.append(values)


class SubscriptionQrContextTests(unittest.TestCase):
    def test_html_decoding_never_turns_a_node_label_into_javascript(self):
        parser=QrParser();parser.feed(render_fixture())
        self.assertEqual(len(parser.buttons),1)
        button=parser.buttons[0]
        executable=' '.join(value or '' for key,value in button.items() if key.lower().startswith('on'))
        self.assertNotIn('pvnDemoXss',executable)
        self.assertEqual(button.get('data-qr-link'),URL)
        self.assertEqual(button.get('data-qr-name'),LABEL)


if __name__=='__main__':unittest.main()
