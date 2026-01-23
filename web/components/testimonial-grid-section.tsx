import React from "react" // Removing Image import

const testimonials = [
  {
    quote:
      "방대한 전공 서적을 언제 다 보나 막막했는데, Project Thunder가 집어준 핵심 위주로 공부해서 A+ 받았습니다! 특히 교수님이 강조하신 부분을 놓치지 않고 짚어준 게 신의 한 수였어요.",
    name: "김민수",
    company: "서울대학교 컴퓨터공학부",
    avatar: "/placeholder.svg?height=40&width=40", // Use placeholder
    type: "large-teal",
  },
  {
    quote:
      "교수님이 수업 시간에 지나가듯 말씀하신 힌트를 정확하게 캐치해서 놀랐어요. 덕분에 시험 문제 적중률이 엄청났습니다.",
    name: "이지은",
    company: "연세대학교 경영학과",
    avatar: "/placeholder.svg?height=40&width=40",
    type: "small-dark",
  },
  {
    quote:
      "취약한 부분만 골라서 오답노트를 만들어주니 공부 효율이 2배로 늘었습니다. 시간 없는 시험 기간에 필수템이에요.",
    name: "박준호",
    company: "고려대학교 기계공학부",
    avatar: "/placeholder.svg?height=40&width=40",
    type: "small-dark",
  },
  {
    quote:
      "시험 전날 밤새 궁금한 거 물어봤는데, 선배보다 더 친절하게 알려주네요. 실시간 질의응답 기능 강추합니다.",
    name: "최수현",
    company: "성균관대학교 약학과",
    avatar: "/placeholder.svg?height=40&width=40",
    type: "small-dark",
  },
  {
    quote:
      "설마 했는데 진짜 시험 문제의 80%가 여기서 나왔습니다. 소름 돋았어요. 친구들한테 비밀로 하고 싶을 정도입니다.",
    name: "정우성",
    company: "한양대학교 전자공학부",
    avatar: "/placeholder.svg?height=40&width=40",
    type: "small-dark",
  },
  {
    quote:
      "중구난방이었던 필기를 체계적으로 정리해줘서 시험 기간에 정말 큰 도움이 되었습니다. 정리의 신이 따로 없어요.",
    name: "강하늘",
    company: "서강대학교 경제학과",
    avatar: "/placeholder.svg?height=40&width=40",
    type: "small-dark",
  },
  {
    quote:
      "복잡한 전공 내용도 이해하기 쉽게 설명해줘서 포기하려던 과목도 살려냈습니다. Project Thunder 덕분에 장학금 탔어요!",
    name: "윤아름",
    company: "이화여자대학교 디자인학부",
    avatar: "/placeholder.svg?height=40&width=40",
    type: "large-light",
  },
]

interface TestimonialCardProps {
  quote: string
  name: string
  company: string
  avatar: string
  type: string
}

const TestimonialCard = ({ quote, name, company, avatar, type }: TestimonialCardProps) => {
  const isLargeCard = type.startsWith("large")
  const avatarSize = isLargeCard ? 48 : 36
  const avatarBorderRadius = isLargeCard ? "rounded-[41px]" : "rounded-[30.75px]"
  const padding = isLargeCard ? "p-6" : "p-[30px]"

  let cardClasses = `flex flex-col justify-between items-start overflow-hidden rounded-[10px] shadow-[0px_2px_4px_rgba(0,0,0,0.08)] relative ${padding}`
  let quoteClasses = ""
  let nameClasses = ""
  let companyClasses = ""
  let backgroundElements = null
  let cardHeight = ""
  const cardWidth = "w-full md:w-[384px]"

  if (type === "large-teal") {
    cardClasses += " bg-primary"
    quoteClasses += " text-primary-foreground text-2xl font-medium leading-8"
    nameClasses += " text-primary-foreground text-base font-normal leading-6"
    companyClasses += " text-primary-foreground/60 text-base font-normal leading-6"
    cardHeight = "h-[502px]"
    backgroundElements = (
      <div
        className="absolute inset-0 w-full h-full bg-cover bg-center bg-no-repeat"
        style={{ backgroundImage: "url('/images/large-card-background.svg')", zIndex: 0 }}
      />
    )
  } else if (type === "large-light") {
    cardClasses += " bg-[rgba(231,236,235,0.12)]"
    quoteClasses += " text-foreground text-2xl font-medium leading-8"
    nameClasses += " text-foreground text-base font-normal leading-6"
    companyClasses += " text-muted-foreground text-base font-normal leading-6"
    cardHeight = "h-[502px]"
    backgroundElements = (
      <div
        className="absolute inset-0 w-full h-full bg-cover bg-center bg-no-repeat opacity-20"
        style={{ backgroundImage: "url('/images/large-card-background.svg')", zIndex: 0 }}
      />
    )
  } else {
    cardClasses += " bg-card outline outline-1 outline-border outline-offset-[-1px]"
    quoteClasses += " text-foreground/80 text-[17px] font-normal leading-6"
    nameClasses += " text-foreground text-sm font-normal leading-[22px]"
    companyClasses += " text-muted-foreground text-sm font-normal leading-[22px]"
    cardHeight = "h-[244px]"
  }

  return (
    <div className={`${cardClasses} ${cardWidth} ${cardHeight}`}>
      {backgroundElements}
      <div className={`relative z-10 font-normal break-words ${quoteClasses}`}>{quote}</div>
      <div className="relative z-10 flex justify-start items-center gap-3">
        <div 
          className={`w-[${avatarSize}px] h-[${avatarSize}px] ${avatarBorderRadius} bg-zinc-700 flex items-center justify-center text-xs font-bold text-zinc-300`}
        >
            {name[0]}
        </div>
        <div className="flex flex-col justify-start items-start gap-0.5">
          <div className={nameClasses}>{name}</div>
          <div className={companyClasses}>{company}</div>
        </div>
      </div>
    </div>
  )
}

export function TestimonialGridSection() {
  return (
    <section className="w-full px-5 overflow-hidden flex flex-col justify-start py-6 md:py-8 lg:py-14">
      <div className="self-stretch py-6 md:py-8 lg:py-14 flex flex-col justify-center items-center gap-2">
        <div className="flex flex-col justify-start items-center gap-4">
          <h2 className="text-center text-foreground text-3xl md:text-4xl lg:text-[40px] font-semibold leading-tight md:leading-tight lg:leading-[40px]">
            Coding made effortless
          </h2>
          <p className="self-stretch text-center text-muted-foreground text-sm md:text-sm lg:text-base font-medium leading-[18.20px] md:leading-relaxed lg:leading-relaxed">
            {"Hear how developers ship products faster, collaborate seamlessly,"} <br />{" "}
            {"and build with confidence using Pointer's powerful AI tools"}
          </p>
        </div>
      </div>
      <div className="w-full pt-0.5 pb-4 md:pb-6 lg:pb-10 flex flex-col md:flex-row justify-center items-start gap-4 md:gap-4 lg:gap-6 max-w-[1100px] mx-auto">
        <div className="flex-1 flex flex-col justify-start items-start gap-4 md:gap-4 lg:gap-6">
          <TestimonialCard {...testimonials[0]} />
          <TestimonialCard {...testimonials[1]} />
        </div>
        <div className="flex-1 flex flex-col justify-start items-start gap-4 md:gap-4 lg:gap-6">
          <TestimonialCard {...testimonials[2]} />
          <TestimonialCard {...testimonials[3]} />
          <TestimonialCard {...testimonials[4]} />
        </div>
        <div className="flex-1 flex flex-col justify-start items-start gap-4 md:gap-4 lg:gap-6">
          <TestimonialCard {...testimonials[5]} />
          <TestimonialCard {...testimonials[6]} />
        </div>
      </div>
    </section>
  )
}
