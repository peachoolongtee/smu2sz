/**
 * Which recording the strategy mocks serve: the opening books' (day 0) until the clock reaches the day the story's news
 * lands (day 34, home.NEWS_DAY), the day-34 books' from then on. The same choice getPlanFunding makes between
 * funding.json and funding_day34.json. Pure, so a unit test can pin it without loading the JSON.
 */
export function pickByDay<T>(day: number, newsDay: number, atDay0: T, atNews: T): T {
  return day >= newsDay ? atNews : atDay0;
}

/**
 * The same choice once the day-34 cure has been approved: before the news day the opening books' recording; from it the day-34
 * books' until the owner approves the cure (home.cureStage() === "approved", the condition under which the home mock serves
 * home_summary_after.json), then the post-approval recording. Pure, so a unit test can pin it.
 */
export function pickByStory<T>(day: number, newsDay: number, approved: boolean, atDay0: T, atNews: T, afterApproval: T): T {
  return day >= newsDay ? (approved ? afterApproval : atNews) : atDay0;
}
