import re

from resource import Resource
from . import Bad4ChanURLError

class Thread(Resource):

    thread_re = re.compile(r'/(?P<board>\w+)/res/(?P<thread>\d+)')

    @staticmethod
    def url(board, thread):
        return 'http://a.4cdn.org/{board}/res/{thread}.json'.format(thread=thread, board=board)

    @staticmethod
    def urlparse(url):
        match = Thread.thread_re.search(url)
        if not match:
            raise Bad4ChanURLError
        return match.groupdict()

    def __init__(self, board, thread, **kwargs):
        self.board = board
        self.thread = thread
        self._images = False

        super(Thread, self).__init__(Thread.url(board, thread), **kwargs)

    @property
    def iter_images(self):
        if self._images:
            for image in self._images:
                yield image
        else:
            self._images = []
            images = [Image.image_from_post_json(post, self.board) for post in self.json["posts"] if post["tim"]]
            for image in images:
                self._images.append(image)
                yield image

    @property
    def images(self):
        self.iter_images()
        return self._images

class Image(Resource):
    @staticmethod
    def url(board, imagename, ext):
        return 'http://i.4cdn.org/{board}/src/{imagename}{ext}'.format(board=board, imagename=imagename, ext=ext)

    @staticmethod
    def url_from_post_json(post_json, board):
        return Image.url(board=board,
                imagename=post_json["tim"],
                ext=post_json["ext"])

    @staticmethod
    def image_from_post_json(post_json, board):
        return Image(board=board,
                imagename=post_json["tim"],
                ext=post_json["ext"])


    def __init__(self, board, imagename, ext, **kwargs):
        self.board = board
        self.imagename = imagename
        self.ext = ext

        super(Image, self).__init__(Image.url(board, imagename, ext), **kwargs)

    @property
    def filename(self):
        return '{imagename}{ext}'.format(imagename=self.imagename, ext=self.ext)
