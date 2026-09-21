/** Builds a smoothed SVG path from series points scaled into a viewBox. */
export function buildPath(points: number[], yMax: number, width: number, height: number): string {
  if (points.length === 0) return ''
  const step = points.length > 1 ? width / (points.length - 1) : 0
  const coords = points.map((point, index) => ({
    x: index * step,
    y: height - Math.min(point / yMax, 1) * height,
  }))

  return coords.reduce((path, point, index) => {
    if (index === 0) return `M${point.x.toFixed(1)},${point.y.toFixed(1)}`
    const previous = coords[index - 1]
    const controlX = (previous.x + point.x) / 2
    return `${path} C${controlX.toFixed(1)},${previous.y.toFixed(1)} ${controlX.toFixed(1)},${point.y.toFixed(1)} ${point.x.toFixed(1)},${point.y.toFixed(1)}`
  }, '')
}

/** Closes a line path into the area beneath it. */
export function toAreaPath(linePath: string, width: number, height: number): string {
  return linePath ? `${linePath} L${width},${height} L0,${height}Z` : ''
}
