# Contributor: Douile <douile@douile.com>
# Maintainer: Douile <douile@douile.com>
pkgname=friends-queue
pkgver=0.1
pkgrel=0
_gitrev=7e48c476022dd1ce9e96bef8c77ec8d936033798
pkgdesc="Share a video queue with your friends "
url="https://github.com/Douile/friends-queue"
arch="all"
license="AGPL-3.0-or-later"
depends="py3-mpv yt-dlp"
makedepends="py3-setuptools"
source="https://github.com/Douile/friends-queue/archive/$_gitrev/friends-queue-$_gitrev.tar.gz"
builddir="$srcdir/friends-queue-$_gitrev"

prepare() {
	default_prepare

	echo "${pkgver%_git*}-$_gitrev" > VERSION
}

build() {
	python3 setup.py build
}

package() {
	python3 setup.py install --prefix=/usr --root="$pkgdir"
}

sha512sums="
1d3d631e3365191386e77723b78341208ba919ad5e0c91cd927def9655b7f67b860e47064b4da1316aab305f0c2d2a760526f03f16c336127bffc8fe05151dd2  friends-queue-7e48c476022dd1ce9e96bef8c77ec8d936033798.tar.gz
"
