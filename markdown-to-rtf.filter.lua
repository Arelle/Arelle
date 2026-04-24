-- Pandoc Lua filter for generating NSIS-friendly RTF from LICENSE.md
-- 1. Sets document default font size to 8pt (\fs16) for the installer license page
-- 2. Flattens hyperlinks to visible URLs (NSIS RichEdit doesn't support \field)
-- 3. Shifts headings down one level to reduce heading sizes

function Meta(meta)
  meta['header-includes'] = pandoc.MetaBlocks({
    pandoc.RawBlock('rtf', '\\fs16')
  })
  return meta
end

function Link(el)
  local text = pandoc.utils.stringify(el.content)
  if text == el.target then
    return pandoc.Str("<" .. el.target .. ">")
  end
  local result = pandoc.List:new()
  for _, item in ipairs(el.content) do
    result:insert(item)
  end
  result:insert(pandoc.Space())
  result:insert(pandoc.Str("<" .. el.target .. ">"))
  return result
end

function Header(el)
  el.level = math.min(el.level + 1, 6)
  return el
end
