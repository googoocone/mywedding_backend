import enum

class HallTypeEnum(str, enum.Enum):
    야외 = "야외"
    호텔 = "호텔"
    가든 = "가든"
    스몰 = "스몰"
    하우스 = "하우스"
    컨벤션 = "컨벤션"
    채플 = "채플"

class MoodEnum(str, enum.Enum):
    밝은 = "밝은"
    어두운 = "어두운"

class EstimateTypeEnum(str, enum.Enum):
    standard = "standard"
    admin = "admin"
    user = "user"

class MealCategoryEnum(str, enum.Enum):
    대인 = "대인"
    소인 = "소인"
    미취학 = "미취학"
    음주류 = "음주류"

class PackageTypeEnum(str, enum.Enum):
    스드메 = "스드메"
    개별 = "개별"

class PackageItemTypeEnum(str, enum.Enum):
    스튜디오 = "스튜디오"
    드레스 = "드레스"
    메이크업 = "메이크업"
