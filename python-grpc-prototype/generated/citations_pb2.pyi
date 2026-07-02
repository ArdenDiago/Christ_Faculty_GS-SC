from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Empty(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class Paper(_message.Message):
    __slots__ = ("title", "link", "citations", "year")
    TITLE_FIELD_NUMBER: _ClassVar[int]
    LINK_FIELD_NUMBER: _ClassVar[int]
    CITATIONS_FIELD_NUMBER: _ClassVar[int]
    YEAR_FIELD_NUMBER: _ClassVar[int]
    title: str
    link: str
    citations: str
    year: str
    def __init__(self, title: _Optional[str] = ..., link: _Optional[str] = ..., citations: _Optional[str] = ..., year: _Optional[str] = ...) -> None: ...

class AuthorPapers(_message.Message):
    __slots__ = ("name", "papers")
    NAME_FIELD_NUMBER: _ClassVar[int]
    PAPERS_FIELD_NUMBER: _ClassVar[int]
    name: str
    papers: _containers.RepeatedCompositeFieldContainer[Paper]
    def __init__(self, name: _Optional[str] = ..., papers: _Optional[_Iterable[_Union[Paper, _Mapping]]] = ...) -> None: ...

class ScopusPaper(_message.Message):
    __slots__ = ("title", "year", "citations", "link")
    TITLE_FIELD_NUMBER: _ClassVar[int]
    YEAR_FIELD_NUMBER: _ClassVar[int]
    CITATIONS_FIELD_NUMBER: _ClassVar[int]
    LINK_FIELD_NUMBER: _ClassVar[int]
    title: str
    year: str
    citations: str
    link: str
    def __init__(self, title: _Optional[str] = ..., year: _Optional[str] = ..., citations: _Optional[str] = ..., link: _Optional[str] = ...) -> None: ...

class AuthorScopusPapers(_message.Message):
    __slots__ = ("name", "papers", "profile_link")
    NAME_FIELD_NUMBER: _ClassVar[int]
    PAPERS_FIELD_NUMBER: _ClassVar[int]
    PROFILE_LINK_FIELD_NUMBER: _ClassVar[int]
    name: str
    papers: _containers.RepeatedCompositeFieldContainer[ScopusPaper]
    profile_link: str
    def __init__(self, name: _Optional[str] = ..., papers: _Optional[_Iterable[_Union[ScopusPaper, _Mapping]]] = ..., profile_link: _Optional[str] = ...) -> None: ...

class CombinedAuthorStats(_message.Message):
    __slots__ = ("name", "papers_google_scholar", "citations_google_scholar", "h_index_google_scholar", "i10_index_google_scholar", "yearly_citations_google_scholar", "papers_scopus", "citations_scopus", "h_index_scopus")
    class YearlyCitationsGoogleScholarEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: int
        def __init__(self, key: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...
    NAME_FIELD_NUMBER: _ClassVar[int]
    PAPERS_GOOGLE_SCHOLAR_FIELD_NUMBER: _ClassVar[int]
    CITATIONS_GOOGLE_SCHOLAR_FIELD_NUMBER: _ClassVar[int]
    H_INDEX_GOOGLE_SCHOLAR_FIELD_NUMBER: _ClassVar[int]
    I10_INDEX_GOOGLE_SCHOLAR_FIELD_NUMBER: _ClassVar[int]
    YEARLY_CITATIONS_GOOGLE_SCHOLAR_FIELD_NUMBER: _ClassVar[int]
    PAPERS_SCOPUS_FIELD_NUMBER: _ClassVar[int]
    CITATIONS_SCOPUS_FIELD_NUMBER: _ClassVar[int]
    H_INDEX_SCOPUS_FIELD_NUMBER: _ClassVar[int]
    name: str
    papers_google_scholar: int
    citations_google_scholar: int
    h_index_google_scholar: int
    i10_index_google_scholar: int
    yearly_citations_google_scholar: _containers.ScalarMap[str, int]
    papers_scopus: int
    citations_scopus: int
    h_index_scopus: int
    def __init__(self, name: _Optional[str] = ..., papers_google_scholar: _Optional[int] = ..., citations_google_scholar: _Optional[int] = ..., h_index_google_scholar: _Optional[int] = ..., i10_index_google_scholar: _Optional[int] = ..., yearly_citations_google_scholar: _Optional[_Mapping[str, int]] = ..., papers_scopus: _Optional[int] = ..., citations_scopus: _Optional[int] = ..., h_index_scopus: _Optional[int] = ...) -> None: ...
