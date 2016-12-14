import posixpath
import productmd.compose
from urlparse import urlparse
from productmd.composeinfo import ComposeInfo
from productmd.images import Images
from productmd.rpms import Rpms
import requests
import bucko.log as log


class OnlineCompose(productmd.compose.Compose):
    """ Compose that can be queried over HTTP

    Note that future productmd versions will support this natively. See
    https://github.com/release-engineering/productmd/pull/53
    """
    def __init__(self, path):
        url = urlparse(path)
        if url.scheme == 'http':
            self.online = True
            super(OnlineCompose, self).__init__('')
        else:
            self.online = False
            super(OnlineCompose, self).__init__(path)
        self.path = path

    def _download(self, filepath):
        """
        Download and return some textual manifest for this compose

        :param str path: eg. 'compose/metadata/composeinfo.json'
        """
        url = posixpath.join(self.path, filepath)
        log.info('Downloading %s' % url)
        r = requests.get(url)
        r.raise_for_status()
        return r.text

    @property
    def info(self):
        if not self.online:
            return super(OnlineCompose, self).info
        if self._composeinfo is not None:
            return self._composeinfo
        text = self._download('compose/metadata/composeinfo.json')
        self._composeinfo = ComposeInfo()
        self._composeinfo.loads(text)

        return self._composeinfo

    @property
    def images(self):
        if not self.online:
            return super(OnlineCompose, self).images
        if self._images is not None:
            return self._images
        text = self._download('compose/metadata/image-manifest.json')
        self._images = Images()
        self._images.loads(text)
        return self._images

    @property
    def rpms(self):
        if not self.online:
            return super(OnlineCompose, self).rpms
        if self._rpms is not None:
            return self._rpms
        text = self._download('compose/metadata/rpm-manifest.json')
        self._rpms = Rpms()
        self._rpms.loads(text)
        return self._rpms
