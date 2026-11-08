/** Deliberately messy function so the JS maintainability scanner has a hotspot. */

export function process(data, flag, mode, extra, unused, debug = false) {
  let total = 0;
  if (data) {
    for (const x of data) {
      if (x) {
        if (flag) {
          if (mode === "a") {
            if (extra) {
              if (debug) {
                total += 1;
              } else if (extra > 2) {
                total += 2;
              } else {
                total += 3;
              }
            } else if (extra === 0) {
              total -= 1;
            }
          } else if (mode === "b") {
            while (total < 10) {
              if (extra && debug) {
                total += 1;
              } else {
                break;
              }
            }
          } else {
            try {
              total += Number(x);
            } catch (err) {
              if (debug) {
                total = 0;
              }
            }
          }
        }
      }
    }
  } else if (flag || extra || debug) {
    total = -1;
  }
  return total;
}
