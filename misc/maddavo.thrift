namespace * maddavo

struct System {
    1:  i32 system_id,
    2:  string name,
    3:  double x,
    4:  double y,
    5:  double z,
    6:  i64 timestamp,
}

struct Station {
    1:  i32 station_id,
    2:  i32 system_id,
    3:  string name,
    4:  i32 ls_from_star,
    5:  byte max_pad_size,
    6:  byte has_black_market,
}

struct Category {
    1:  byte category_id,
    2:  string name,
}

struct Item {
    1:  byte item_id,
    2:  byte category_id,
    3:  string name,
}

struct Price {
    1:  byte item_id,
    2:  i16 price,
    3:  optional i32 uints,
    4:  optional byte level,    
}

struct Prices {
    1:  i32 station_id,
    2:  list<Price> buying,
    3:  list<Price> selling,
}

struct Response {
    1:  i64 timestamp,
    2:  list<System> systems,
    3:  list<Station> stations,
    4:  list<Category> categories,
    5:  list<Item> items,
    6:  list<Prices> prices,
}