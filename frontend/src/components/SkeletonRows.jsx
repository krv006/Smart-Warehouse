export default function SkeletonRows({ count = 4 }) {
  return (
    <div className="skeleton-wrap" aria-hidden="true">
      {Array.from({ length: count }, (_, index) => <i key={index} />)}
    </div>
  )
}
