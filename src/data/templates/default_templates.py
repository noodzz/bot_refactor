# Шаблоны проектов
DEFAULT_TEMPLATES = {
    1: {
        "name": "1 поток",
        "tasks": [
            {
                "name": "Расчёт стоимостей",
                "duration": 3,
                "predecessors": [],
                "position": "Проектный менеджер",
                "is_group": False
            },
            {
                "name": "Создание тарифов обучения",
                "duration": 1,
                "predecessors": ["Расчёт стоимостей"],
                "position": "Технический специалист",
                "is_group": False
            },
            {
                "name": "Создание продуктовых типов и продуктов",
                "duration": 2,
                "predecessors": ["Создание тарифов обучения"],
                "position": "Настройка",
                "is_group": True,
                "subtasks": [
                    {
                        "name": "Собрать таблицу для скрипта",
                        "duration": 1,
                        "position": "Технический специалист",
                        "parallel": False
                    },
                    {
                        "name": "Создать продукты и ПТ",
                        "duration": 1,
                        "position": "Старший технический специалист",
                        "parallel": False
                    }
                ]
            },
            {
                "name": "Создание потоков обучения",
                "duration": 2,
                "predecessors": ["Создание продуктовых типов и продуктов"],
                "position": "Настройка",
                "is_group": True,
                "subtasks": [
                    {
                        "name": "Собрать таблицу для скрипта",
                        "duration": 1,
                        "position": "Технический специалист",
                        "parallel": False
                    },
                    {
                        "name": "Создать потоки",
                        "duration": 1,
                        "position": "Старший технический специалист",
                        "parallel": False
                    }
                ]
            },
            {
                "name": "Создание тарифов для внешнего сайта",
                "duration": 1,
                "predecessors": ["Создание тарифов обучения"],
                "position": "Старший технический специалист",
                "is_group": False
            },
            {
                "name": "Создание продуктовых страниц для внешнего сайта",
                "duration": 1,
                "predecessors": ["Создание продуктовых типов и продуктов"],
                "position": "Старший технический специалист",
                "is_group": False
            },
            {
                "name": "Создание продуктовых типов для внешнего сайта",
                "duration": 1,
                "predecessors": ["Создание продуктовых типов и продуктов"],
                "position": "Старший технический специалист",
                "is_group": False
            },
            {
                "name": "Сборка и загрузка образовательных программ",
                "duration": 2,
                "predecessors": ["Создание продуктовых типов для внешнего сайта"],
                "position": "Настройка",
                "is_group": True,
                "subtasks": [
                    {
                        "name": "Собрать таблицу для скрипта",
                        "duration": 1,
                        "position": "Технический специалист",
                        "parallel": False
                    },
                    {
                        "name": "Запустить скрипт",
                        "duration": 1,
                        "position": "Старший технический специалист",
                        "parallel": False
                    }
                ]
            },
            {
                "name": "Создание настроек групп учеников",
                "duration": 1,
                "predecessors": ["Создание продуктовых типов и продуктов"],
                "position": "Руководитель настройки",
                "is_group": False
            },
            {
                "name": "Создание пакетных предложений",
                "duration": 1,
                "predecessors": ["Создание потоков обучения"],
                "position": "Старший технический специалист",
                "is_group": False
            },
            {
                "name": "Создание комплектов курсов",
                "duration": 1,
                "predecessors": ["Создание пакетных предложений"],
                "position": "Старший технический специалист",
                "is_group": False
            },
            {
                "name": "Создание связей с подарочными курсами",
                "duration": 1,
                "predecessors": ["Создание пакетных предложений"],
                "position": "Технический специалист",
                "is_group": False
            },
            {
                "name": "Настройка порядка карточек в каталоге",
                "duration": 1,
                "predecessors": ["Создание продуктовых типов и продуктов"],
                "position": "Технический специалист",
                "is_group": False
            },
            {
                "name": "Настройка актуального месяца покупки",
                "duration": 1,
                "predecessors": ["Создание потоков обучения"],
                "position": "Старший технический специалист",
                "is_group": False
            },
            {
                "name": "Импорт академических часов",
                "duration": 2,
                "predecessors": ["Создание потоков обучения"],
                "position": "Технический специалист",
                "is_group": False
            },
            {
                "name": "Постконтроль созданных объектов",
                "duration": 2,
                "predecessors": ["Создание тарифов для внешнего сайта", "Создание продуктовых страниц для внешнего сайта",
                                 "Сборка и загрузка образовательных программ на внешний сайт", "Создание настроек групп учеников",
                                 "Создание комплектов курсов", "Создание связей с подарочными курсами",
                                 "Настройка порядка карточек в каталоге", "Настройка актуального месяца покупки",
                                 "Импорт академических часов"],
                "position": "Настройка",
                "is_group": True,
                "subtasks": [
                    {
                        "name": "Постконтроль объектов",
                        "duration": 2,
                        "position": "Старший технический специалист",
                        "parallel": True
                    },
                    {
                        "name": "Постконтроль объектов",
                        "duration": 2,
                        "position": "Старший технический специалист",
                        "parallel": True
                    },
                    {
                        "name": "Постконтроль объектов",
                        "duration": 2,
                        "position": "Руководитель настройки",
                        "parallel": True
                    }
                ]
            },
            {
                "name": "Создание модулей обучения",
                "duration": 2,
                "predecessors": [],
                "position": "Контент",
                "is_group": True,
                "subtasks": [
                    {
                        "name": "Подготовить таблицу для модулей",
                        "duration": 1,
                        "position": "Младший специалист",
                        "parallel": False
                    },
                    {
                        "name": "Создать модули",
                        "duration": 1,
                        "position": "Руководитель контента",
                        "parallel": False
                    }
                ]
            },
            {
                "name": "Создание уровней обучения",
                "duration": 2,
                "predecessors": [],
                "position": "Контент",
                "is_group": True,
                "subtasks": [
                    {
                        "name": "Подготовить таблицу для уровней",
                        "duration": 1,
                        "position": "Младший специалист",
                        "parallel": False
                    },
                    {
                        "name": "Создать уровни",
                        "duration": 1,
                        "position": "Руководитель контента",
                        "parallel": False
                    }
                ]
            },
            {
                "name": "Настройка связей между потоками и модулями",
                "duration": 1,
                "predecessors": ["Создание потоков обучения", "Создание модулей обучения"],
                "position": "Старший специалист",
                "is_group": False
            },
            {
                "name": "Настройка связей между потоками и уровнями",
                "duration": 1,
                "predecessors": ["Создание потоков обучения", "Создание уровней обучения"],
                "position": "Старший специалист",
                "is_group": False
            },
            {
                "name": "Сборка сводной таблицы для создания занятий",
                "duration": 7,
                "predecessors": ["Настройка связей между потоками и модулями","Настройка связей между потоками и уровнями"],
                "position": "Контент",
                "is_group": True,
                "subtasks": [
                    {
                        "name": "Сборка сводной",
                        "duration": 7,
                        "position": "Старший специалист",
                        "parallel": True
                    },
                    {
                        "name": "Сборка сводной",
                        "duration": 7,
                        "position": "Старший специалист",
                        "parallel": True
                    },
                    {
                        "name": "Сборка сводной",
                        "duration": 7,
                        "position": "Старший специалист",
                        "parallel": True
                    },
                    {
                        "name": "Сборка сводной",
                        "duration": 7,
                        "position": "Руководитель контента",
                        "parallel": True
                    }
                ]
            },
            {
                "name": "Создание занятий и домашних заданий",
                "duration": 3,
                "predecessors": ["Сборка сводной таблицы для создания занятий"],
                "position": "Руководитель контента",
                "is_group": False
            },
            {
                "name": "Создание связей между уроками и модулями",
                "duration": 1,
                "predecessors": ["Создание занятий и домашних заданий"],
                "position": "Контент",
                "is_group": True,
                "subtasks": [
                    {
                        "name": "Создание урок-модуль",
                        "duration": 1,
                        "position": "Старший специалист",
                        "parallel": True
                    },
                    {
                        "name": "Создание урок-модуль",
                        "duration": 1,
                        "position": "Старший специалист",
                        "parallel": True
                    },
                    {
                        "name": "Создание урок-модуль",
                        "duration": 1,
                        "position": "Старший специалист",
                        "parallel": True
                    }
                ]
            },
            {
                "name": "Создание связей продукт-урок-уровень",
                "duration": 2,
                "predecessors": ["Создание занятий и домашних заданий"],
                "position": "Контент",
                "is_group": True,
                "subtasks": [
                    {
                        "name": "Создание связей продукт-урок-уровень",
                        "duration": 2,
                        "position": "Старший специалист",
                        "parallel": True
                    },
                    {
                        "name": "Создание связей продукт-урок-уровень",
                        "duration": 2,
                        "position": "Старший специалист",
                        "parallel": True
                    },
                    {
                        "name": "Создание связей продукт-урок-уровень",
                        "duration": 2,
                        "position": "Старший специалист",
                        "parallel": True
                    }
                ]
            },
            {
                "name": "Наполнение контентом занятий и домашних заданий",
                "duration": 3,
                "predecessors": ["Создание связей продукт-урок-уровень"],
                "position": "Контент",
                "is_group": True,
                "subtasks": [
                    {
                        "name": "Перенос наполнения",
                        "duration": 3,
                        "position": "Младший специалист",
                        "parallel": True
                    },
                    {
                        "name": "Перенос наполнения",
                        "duration": 3,
                        "position": "Младший специалист",
                        "parallel": True
                    },
                    {
                        "name": "Перенос наполнения",
                        "duration": 3,
                        "position": "Младший специалист",
                        "parallel": True
                    },
                    {
                        "name": "Перенос наполнения",
                        "duration": 3,
                        "position": "Младший специалист",
                        "parallel": True
                    },
                    {
                        "name": "Перенос наполнения",
                        "duration": 3,
                        "position": "Младший специалист",
                        "parallel": True
                    }
                ]
            },
            {
                "name": "Постконтроль созданных уроков",
                "duration": 7,
                "predecessors": ["Создание связей продукт-урок-уровень"],
                "position": "Контент",
                "is_group": True,
                "subtasks": [
                    {
                        "name": "Постконтроль",
                        "duration": 7,
                        "position": "Младший специалист",
                        "parallel": True
                    },
                    {
                        "name": "Постконтроль",
                        "duration": 7,
                        "position": "Младший специалист",
                        "parallel": True
                    },
                    {
                        "name": "Постконтроль",
                        "duration": 7,
                        "position": "Младший специалист",
                        "parallel": True
                    },
                    {
                        "name": "Постконтроль",
                        "duration": 7,
                        "position": "Младший специалист",
                        "parallel": True
                    },
                    {
                        "name": "Постконтроль",
                        "duration": 7,
                        "position": "Младший специалист",
                        "parallel": True
                    },
                    {
                        "name": "Постконтроль",
                        "duration": 7,
                        "position": "Младший специалист",
                        "parallel": True
                    }
                ]
            }
        ]
    },
    2: {
        "name": "Бесплатный курс с уровнями",
        "tasks": [
            {
                "name": "Создание продуктовых типов и продуктов",
                "duration": 2,
                "predecessors": [],
                "position": "Настройка",
                "is_group": True,
                "subtasks": [
                    {
                        "name": "Таблица для скрипта",
                        "duration": 1,
                        "position": "Технический специалист",
                        "parallel": False
                    },
                    {
                        "name": "Создание продуктов и ПТ",
                        "duration": 1,
                        "position": "Старший технический специалист",
                        "parallel": False
                    }
                ]
            },
            {
                "name": "Создание потоков обучения",
                "duration": 2,
                "predecessors": ["Создание продуктовых типов и продуктов"],
                "position": "Настройка",
                "is_group": True,
                "subtasks": [
                    {
                        "name": "Таблица для скрипта",
                        "duration": 1,
                        "position": "Технический специалист",
                        "parallel": False
                    },
                    {
                        "name": "Создание потоков",
                        "duration": 1,
                        "position": "Старший технический специалист",
                        "parallel": False
                    }
                ]
            },
            {
                "name": "Постконтроль созданных объектов",
                "duration": 1,
                "predecessors": ["Создание потоков обучения"],
                "position": "Руководитель настройки",
                "is_group": False
            },
            {
                "name": "Создание уровней",
                "duration": 2,
                "predecessors": [],
                "position": "Контент",
                "is_group": True,
                "subtasks": [
                    {
                        "name": "Создание уровней 1",
                        "duration": 2,
                        "position": "Старший специалист",
                        "parallel": True
                    },
                    {
                        "name": "Создание уровней 2",
                        "duration": 2,
                        "position": "Старший специалист",
                        "parallel": True
                    }
                ]
            },
        ]
    }
}