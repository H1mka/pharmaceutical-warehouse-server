def generate_pagination(request, total_items):
  page_raw = request.GET.get("page", "1")
  page_size_raw = request.GET.get("page_size", "10")

  try:
    page = int(page_raw)
    page_size = int(page_size_raw)
  except (TypeError, ValueError):
    raise ValueError("Query params 'page' and 'page_size' must be integers")

  if page <= 0 or page_size <= 0:
    raise ValueError("Query params 'page' and 'page_size' must be positive integers")

  page_size = min(page_size, 100)
  total_pages = max(1, (total_items + page_size - 1) // page_size)

  print(page, total_pages, total_items)

  if page > total_pages and total_items > 0:
    raise ValueError("Page is out of range")

  skip = (page - 1) * page_size
  pagination_data = {
    "page": page,
    "page_size": page_size,
    "total_items": total_items,
    "total_pages": total_pages
  }

  return pagination_data, skip
