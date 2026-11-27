"""Assert the real arrangement of grid children, not CSS serialization.

Chromium's fieldset layout uses an anonymous content box; computed grid tracks
may remain a repeat()/minmax() expression rather than resolved pixel widths.
"""


def assert_grid_rows(items, columns, total):
    """Check every visible item is in the expected row, in DOM order."""
    assert columns > 0 and total > 0
    items.last.wait_for(state='visible')
    boxes = items.evaluate_all('''els => els.map(el => {
      const {x, y, width, height} = el.getBoundingClientRect();
      return {x, y, width, height};
    })''')
    assert len(boxes) == total, (columns, total, boxes)
    rows = []
    for box in boxes:
        assert box['width'] > 0 and box['height'] > 0, box
        if not rows or abs(box['y'] - rows[-1][0]['y']) > 1:
            rows.append([])
        rows[-1].append(box)
    expected = [min(columns, total - start) for start in range(0, total, columns)]
    assert [len(row) for row in rows] == expected, (expected, rows)
    for row in rows:
        for left, right in zip(row, row[1:]):
            assert left['x'] + left['width'] <= right['x'] + 1, row
    for upper, lower in zip(rows, rows[1:]):
        assert max(b['y'] + b['height'] for b in upper) <= lower[0]['y'] + 1, (upper, lower)
