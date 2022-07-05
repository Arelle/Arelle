# Use oldest LTS release for linked glibc compatibility
FROM registry.redhat.io/rhel7:7.9

ARG PYTHON_VERSION
ARG TCLTK_VERSION
ENV LD_LIBRARY_PATH=/usr/local/lib

RUN --mount=type=secret,id=redhat_username \
    --mount=type=secret,id=redhat_password \
    subscription-manager register \
    --username $(cat /run/secrets/redhat_username) \
    --password $(cat /run/secrets/redhat_password) \
    --auto-attach \
    && yum -y update \
    && yum -y groupinstall "Development Tools" \
    && yum -y install \
        bzip2-devel \
        gcc \
        gdbm-devel \
        git \
        libffi-devel \
        libuuid-devel \
        libX11-devel \
        libxml2-devel \
        libxslt-devel \
        ncurses-devel \
        openssl-devel \
        readline-devel \
        sqlite-devel \
        unixODBC-devel \
        wget \
    && yum autoremove -y \
    && yum clean all \
    && rm -rf /var/cache/yum \
    ; subscription-manager unregister

WORKDIR /tmp

RUN wget https://sourceforge.net/projects/tcl/files/Tcl/${TCLTK_VERSION}/tcl${TCLTK_VERSION}-src.tar.gz \
    && tar xzf tcl${TCLTK_VERSION}-src.tar.gz \
    && (cd tcl${TCLTK_VERSION}/unix \
        && ./configure \
        && make install --jobs "$(nproc)") \
    && rm -r ./tcl${TCLTK_VERSION} \
    && rm tcl${TCLTK_VERSION}-src.tar.gz

RUN wget https://sourceforge.net/projects/tcl/files/Tcl/${TCLTK_VERSION}/tk${TCLTK_VERSION}-src.tar.gz \
    && tar xzf tk${TCLTK_VERSION}-src.tar.gz \
    && (cd tk${TCLTK_VERSION}/unix \
        && ./configure \
        && make install --jobs "$(nproc)") \
    && rm -r ./tk${TCLTK_VERSION} \
    && rm tk${TCLTK_VERSION}-src.tar.gz

RUN wget https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz \
    && tar xzf Python-${PYTHON_VERSION}.tgz \
    && (cd Python-${PYTHON_VERSION} \
        && ./configure \
            --enable-optimizations \
            --enable-shared \
            --with-computed-gotos \
            --with-lto \
            --with-system-ffi \
        && make install --jobs "$(nproc)") \
    && rm -r ./Python-${PYTHON_VERSION} \
    && rm ./Python-${PYTHON_VERSION}.tgz

RUN pip3 install --upgrade pip setuptools wheel

WORKDIR /build

ADD ../requirements*.txt .

RUN pip3 install -r requirements-dev.txt

ADD ../ /build

RUN /bin/sh ./scripts/buildLinuxDist.sh redhat

ENTRYPOINT ["/bin/sh", "-c"]
