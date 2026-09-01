from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator

DEFAULT_PAGE_SIZE = 25


def paginate(request, queryset, per_page: int = DEFAULT_PAGE_SIZE, page_param: str = "page"):
    """Server-side pagination for list views.

    Returns ``(page, querystring)`` where *querystring* preserves the active
    GET filters so pager links only change the page number.
    """
    paginator = Paginator(queryset, per_page)
    raw = request.GET.get(page_param) or 1
    try:
        page = paginator.page(raw)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)
    params = request.GET.copy()
    params.pop(page_param, None)
    return page, params.urlencode()
