import requests
from clint.textui import progress

class Resource(object):
    def __init__(self, url, get_with_progress_bar=False, session=False):
        self.url = url
        if not session:
            self.session = requests.Session()
        else:
            self.session = session

        self.get_with_progress_bar = get_with_progress_bar
        self.progress_bar_label = self.url

        self._length = False

        self._response = False
        self._content = False
        self._text = False
        self._json = False


    @property
    def length(self):
        if self._length == False:
            self._length = self.response.headers.get('content-length')
            if self._length:
                self._length = int(self._length)
        return self._length

    @property
    def response(self):
        if self._response == False:
            self._response = self.session.get(self.url, stream=self.get_with_progress_bar)
            # raise error only if not OK response
            self._response.raise_for_status()
        return self._response

    @property
    def content(self):
        if self._content == False:
            if self.get_with_progress_bar:
                self._content = ""
                for chunk in progress.bar(self.response.iter_content(chunk_size=1024), label='%s: ' % self.progress_bar_label, expected_size=(self.length/1024) + 1):
                    if chunk:
                        self._content += chunk
            else:
                self._content = self.response.content
        return self._content

    @property
    def text(self):
        if self._text == False:
            self._text = self.response.text
        return self._text

    @property
    def json(self):
        if self._json == False:
            self._json = self.response.json()
        return self._json

    def save(self, fobj):
        fobj.write(self.content)
