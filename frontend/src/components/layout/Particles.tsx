/** How many motes drift up the page. Enough to notice, few enough to ignore. */
const COUNT = 22

/** A small deterministic generator, so the layout is identical on every mount. */
function layout() {
  let seed = 20260914
  const next = () => {
    seed = (seed * 1664525 + 1013904223) % 4294967296
    return seed / 4294967296
  }
  return Array.from({ length: COUNT }, (_, index) => {
    const size = 2 + next() * 4
    return {
      id: index,
      left: `${next() * 100}%`,
      size: `${size}px`,
      delay: `${next() * 15}s`,
      duration: `${10 + next() * 20}s`,
    }
  })
}

/** Computed once for the module: the motes never need to be reshuffled. */
const MOTES = layout()

/**
 * The drifting background motes.
 *
 * The layer sits behind everything and takes no pointer events, and it
 * disappears entirely for anyone who asked for reduced motion.
 */
export function Particles() {
  return (
    <div className="particles" aria-hidden="true">
      {MOTES.map((mote) => (
        <span
          key={mote.id}
          className="particle"
          style={{
            left: mote.left,
            width: mote.size,
            height: mote.size,
            animationDelay: mote.delay,
            animationDuration: mote.duration,
          }}
        />
      ))}
    </div>
  )
}
