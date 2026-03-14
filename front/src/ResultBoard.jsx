import Masonry from 'react-masonry-css'

const breakpointCols = {
  default: 4,
  1280: 3,
  768: 2,
  480: 2,
}

export default function ResultBoard({ likedProjects, onReset }) {
  return (
    <div className="min-h-screen bg-[#0f0f0f] px-4 py-6">
      {/* Header */}
      <div className="text-center mb-6">
        <h1 className="text-3xl font-bold text-white">Your Picks</h1>
        <p className="text-gray-400 mt-1 text-sm">
          {likedProjects.length > 0
            ? `You liked ${likedProjects.length} building${likedProjects.length > 1 ? 's' : ''}`
            : 'You didn\'t like any buildings — try again!'}
        </p>
      </div>

      {likedProjects.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <span className="text-6xl">😢</span>
          <p className="text-gray-400">No buildings liked yet.</p>
        </div>
      ) : (
        <Masonry
          breakpointCols={breakpointCols}
          className="masonry-grid"
          columnClassName="masonry-grid-col"
        >
          {likedProjects.map((building) => (
            <div
              key={building.building_id}
              className="mb-3 rounded-xl overflow-hidden relative group cursor-pointer"
            >
              <img
                src={building.imageUrl}
                alt={building.title}
                className="w-full object-cover block"
                loading="lazy"
              />
              {/* Hover overlay */}
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex flex-col justify-end p-3">
                <p className="text-white text-sm font-semibold leading-tight">
                  {building.title}
                </p>
                <p className="text-gray-300 text-xs mt-0.5">{building.architects}</p>
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {building.tags.map((tag) => (
                    <span
                      key={tag}
                      className="bg-white/20 text-white text-[10px] px-2 py-0.5 rounded-full"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </Masonry>
      )}

      {/* Reset Button */}
      <div className="flex justify-center mt-8">
        <button
          onClick={onReset}
          className="bg-white text-black font-semibold px-8 py-3 rounded-full hover:bg-gray-200 transition-colors"
        >
          Start Over
        </button>
      </div>
    </div>
  )
}
