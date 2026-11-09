---
title: "Kitchen Sink Article"
date: 2026-11-05
tags: [markdown, json, test]
authors:
  - Archer
---

# Heading level 1

## Heading level 2 ##

### Heading level 3
#### Heading level 4
##### Heading level 5
###### Heading level 6

Alt Heading level 1
===================

Alt Heading level 2
-------------------

### My Great Heading {#custom-id}

I really like using Markdown.

I think I'll use it to format all of my documents from now on.

This is the first line.  
And this is the second line.
This line uses a backslash\
break. And this is a soft
line break.

I just love **bold text**. I just love __bold text__. Love**is**bold.

Italicized text is the *cat's meow*. Italicized text is the _cat's meow_. A*cat*meow.

This text is ***really important***. This text is ___really important___.
This text is __*really important*__. This text is **_really important_**.
This is really***very***important text.

> Dorothy followed her through many of the beautiful rooms in her castle.
>
> The Witch bade her clean the pots and kettles and sweep the floor.
>
>> The Witch bade her clean the pots and kettles and sweep the floor.

> #### The quarterly results look great!
>
> - Revenue was off the chart.
> - Profits were higher than ever.
>
>  *Everything* is going according to **plan**.

1. First item
2. Second item
3. Third item
    1. Indented item
    2. Indented item
4. Fourth item

Same number list:

1. First item
1. Second item
1. Third item

Starting at eight:

8. Eighth
9. Ninth
10. Tenth

- First item
- Second item
- Third item
    - Indented item
    - Indented item
- Fourth item

Star list:

* First item
* Second item

+ First item
+ Second item

Escaped number:

- 1968\. A great year!
- I think 1969 was second best.

Paragraph in list:

* This is the first list item.
* Here's the second list item.

    I need to add another paragraph below the second list item.

* And here's the third list item.

Blockquote in list:

* This is the first list item.
* Here's the second list item.

    > A blockquote would look great below the second list item.

* And here's the third list item.

Code in list:

1. Open the file.
2. Find the following code block on line 21:

        <html>
          <head>
            <title>Test</title>
          </head>

3. Update the title to match the name of your website.

Image in list:

1. Open the file containing the Linux mascot.
2. Marvel at its beauty.

    ![Tux, the Linux mascot](/assets/images/tux.png)

3. Close the file.

At the command prompt, type `nano`.

``Use `code` in your Markdown file.``

    <html>
      <head>
      </head>
    </html>

***

---

_________________

Try to put a blank line before...

---

...and after a horizontal rule.

My favorite search engine is [Duck Duck Go](https://duckduckgo.com).

My favorite search engine is [Duck Duck Go](https://duckduckgo.com "The best search engine for privacy").

<https://www.markdownguide.org>
<fake@example.com>

I love supporting the **[EFF](https://eff.org)**.
This is the *[Markdown Guide](https://www.markdownguide.org)*.
See the section on [`code`](#code).

[link](https://www.example.com/my%20great%20page)

In a hole in the ground there lived a hobbit. Not a nasty, dirty, wet hole, filled with the ends
of worms and an oozy smell, nor yet a dry, bare, sandy hole with nothing in it to sit down on or to
eat: it was a [hobbit-hole][1], and that means comfort.

[1]: <https://en.wikipedia.org/wiki/Hobbit#Lifestyle> "Hobbit lifestyles"

Collapsed [Hobbit][] and shortcut [hobbit] references.

[hobbit]: https://en.wikipedia.org/wiki/Hobbit 'Hobbits'

![The San Juan Mountains are beautiful!](/assets/images/san-juan-mountains.jpg "San Juan Mountains")

[![An old rock in the desert](/assets/images/shiprock.jpg "Shiprock, New Mexico by Beau Rogers")](https://www.flickr.com/photos/beaurogers/31833779864/in/photolist-Qv3rFw-34mt9F-a9Cmfy-5Ha3Zi-9msKdv-o3hgjr-hWpUte-4WMsJ1-KUQ8N-deshUb-vssBD-6CQci6-8AFCiD-zsJWT-nNfsgB-dPDwZJ-bn9JGn-5HtSXY-6CUhAL-a4UTXB-ugPum-KUPSo-fBLNm-6CUmpy-4WMsc9-8a7D3T-83KJev-6CQ2bK-nNusHJ-a78rQH-nw3NvT-7aq2qf-8wwBso-3nNceh-ugSKP-4mh4kh-bbeeqH-a7biME-q3PtTf-brFpgb-cg38zw-bXMZc-nJPELD-f58Lmo-bXMYG-bz8AAi-bxNtNT-bXMYi-bXMY6-bXMYv)

\* Without the backslash, this would be a bullet in an unordered list.

Escapes: \\ \` \* \_ \{ \} \[ \] \< \> \( \) \# \+ \- \. \! \|

This **word** is bold. This <em>word</em> is italic.

<div class="callout">
  <p>Raw HTML block stays untouched.</p>
</div>

<!-- a comment block -->

| Syntax      | Description |
| ----------- | ----------- |
| Header      | Title       |
| Paragraph   | Text        |

| Syntax | Description | Test Text |
| :--- | :----: | ---: |
| Header | Title | Here's this |
| Paragraph | Text | And more |
| Pipe \| inside | `a \| b` | **bold** |

```
{
  "firstName": "John",
  "lastName": "Smith",
  "age": 25
}
```

```json
{
  "firstName": "John",
  "lastName": "Smith",
  "age": 25
}
```

~~~python title="example.py"
print("```fences inside```")
~~~

Here's a simple footnote,[^1] and here's a longer one.[^bignote]

[^1]: This is the first footnote.

[^bignote]: Here's one with multiple paragraphs and code.

    Indent paragraphs to include them in the footnote.

    `{ my code }`

    Add as many paragraphs as you like.

First Term
: This is the definition of the first term.

Second Term
: This is one definition of the second term.
: This is another definition of the second term.

~~The world is flat.~~ We now know that the world is round.

- [x] Write the press release
- [ ] Update the website
- [ ] Contact the media

Gone camping! :tent: Be back soon.

That is so funny! :joy: :+1:

I need to highlight these ==very important words==.

H~2~O

X^2^

https://www.example.com
Visit www.markdownguide.org, or https://example.com/path_(with)_parens.

Literal chars: 2 * 3 * 4, snake_case_name, 5 > 3, a ~ b, x^y, 10:30:45, a = b, a == b.
